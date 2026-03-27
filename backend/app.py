import os
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from backend.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, CORS_ORIGINS, MAX_MESSAGE_LENGTH
from backend.database import (
    init_db, get_portfolio, add_position, delete_position,
    get_watchlist, add_watchlist_item, remove_watchlist_item,
)
from backend.yahoo_service import get_realtime_quote, get_portfolio_summary, get_market_status
from backend.agent import chat, chat_stream

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend", "static"),
    template_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
)
CORS(app, origins=CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else "*")

# Initialize database on startup
init_db()


# --- Serve Frontend ---

@app.route("/")
def index():
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "..", "frontend"), "index.html"
    )


# --- Health Check ---

@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "service": "StocksAgent"})


# --- Chat API ---

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required"}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"}), 400

    session_id = data.get("session_id", "default")

    try:
        reply = chat(session_id, message)
        return jsonify({"reply": reply, "session_id": session_id})
    except Exception as e:
        return jsonify({"error": f"Agent error: {str(e)}"}), 500


# --- Streaming Chat API (SSE) ---

@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "Message is required"}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"}), 400

    session_id = data.get("session_id", "default")

    def generate():
        try:
            yield from chat_stream(session_id, message)
        except Exception as e:
            import json
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# --- Quote API ---

@app.route("/api/quote/<ticker>")
def api_quote(ticker):
    if not ticker or not ticker.isalnum():
        return jsonify({"error": "Invalid ticker"}), 400
    try:
        quote = get_realtime_quote(ticker)
        return jsonify(quote)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Market Status API ---

@app.route("/api/market/status")
def api_market_status():
    try:
        status = get_market_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Portfolio API ---

@app.route("/api/portfolio", methods=["GET"])
def api_get_portfolio():
    positions = get_portfolio()
    enriched = get_portfolio_summary(positions)
    total_value = sum(p.get("market_value", 0) for p in enriched if p.get("market_value"))
    total_cost = sum(p.get("cost_basis", 0) for p in enriched if p.get("cost_basis"))
    total_pnl = total_value - total_cost
    return jsonify({
        "positions": enriched,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_percent": round((total_pnl / total_cost * 100), 2) if total_cost else 0,
    })


@app.route("/api/portfolio", methods=["POST"])
def api_add_position():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Data is required"}), 400

    ticker = data.get("ticker", "").strip().upper()
    shares = data.get("shares")
    avg_price = data.get("avg_price")

    if not ticker or not ticker.isalpha():
        return jsonify({"error": "Valid ticker is required"}), 400
    if shares is None or float(shares) <= 0:
        return jsonify({"error": "Shares must be positive"}), 400
    if avg_price is None or float(avg_price) <= 0:
        return jsonify({"error": "Average price must be positive"}), 400

    position = add_position(ticker, float(shares), float(avg_price))
    return jsonify(position), 201


@app.route("/api/portfolio/<int:position_id>", methods=["DELETE"])
def api_delete_position(position_id):
    deleted = delete_position(position_id)
    if deleted:
        return jsonify({"success": True})
    return jsonify({"error": "Position not found"}), 404


# --- Watchlist API ---

@app.route("/api/watchlist", methods=["GET"])
def api_get_watchlist():
    items = get_watchlist()
    enriched = []
    for item in items:
        try:
            quote = get_realtime_quote(item["ticker"])
            enriched.append({
                **item,
                "price": quote.get("price"),
                "change": quote.get("change"),
                "change_percent": quote.get("change_percent"),
            })
        except Exception:
            enriched.append({**item, "price": None, "error": "Failed to fetch price"})
    return jsonify({"items": enriched, "count": len(enriched)})


@app.route("/api/watchlist", methods=["POST"])
def api_add_watchlist():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Data is required"}), 400

    ticker = data.get("ticker", "").strip().upper()
    notes = data.get("notes", "").strip()

    if not ticker or not ticker.isalpha():
        return jsonify({"error": "Valid ticker is required"}), 400

    try:
        item = add_watchlist_item(ticker, notes)
        return jsonify(item), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/api/watchlist/<ticker>", methods=["DELETE"])
def api_delete_watchlist(ticker):
    if not ticker or not ticker.isalnum():
        return jsonify({"error": "Invalid ticker"}), 400
    deleted = remove_watchlist_item(ticker.upper())
    if deleted:
        return jsonify({"success": True})
    return jsonify({"error": "Ticker not found in watchlist"}), 404


def main():
    print(f"\n🚀 StocksAgent running at http://localhost:{FLASK_PORT}\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)


if __name__ == "__main__":
    main()
