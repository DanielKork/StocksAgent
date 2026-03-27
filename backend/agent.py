import json
import os
from openai import OpenAI
from backend.config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    AGENT_MAX_ITERATIONS, AGENT_TEMPERATURE, AGENT_CHAT_HISTORY_LIMIT,
    SYSTEM_PROMPT_PATH,
)
from backend import yahoo_service, database

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def _load_system_prompt() -> str:
    """Load system prompt from file. Falls back to a minimal prompt if file is missing."""
    try:
        path = SYSTEM_PROMPT_PATH
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(__file__), "..", path)
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are StocksAgent, a financial assistant. Use the provided tools to fetch live data."


SYSTEM_PROMPT = _load_system_prompt()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_realtime_quote",
            "description": "Get the current real-time quote for a stock including price, change, volume, market cap, 52-week range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_data",
            "description": "Get historical OHLCV price data for a stock. Useful for analyzing price trends over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "period": {"type": "string", "description": "Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"},
                    "interval": {"type": "string", "description": "Data interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get company profile information including sector, industry, description, PE ratio, EPS, dividend yield, beta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financials",
            "description": "Get company financial statements: income statement, balance sheet, and cash flow (annual and quarterly).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get the latest news articles and headlines for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Get analyst recommendations, price targets, and recent rating changes for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "Get technical analysis indicators for a stock: RSI, MACD, SMA, EMA, Bollinger Bands, ATR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "period": {"type": "string", "description": "Historical period to analyze: 3mo, 6mo, 1y, 2y"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": "Compare multiple stocks side by side on key metrics (price, market cap, PE, EPS, dividend yield, beta, sector).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {"type": "array", "items": {"type": "string"}, "description": "List of ticker symbols to compare"}
                },
                "required": ["tickers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Get the user's current portfolio positions with live price data, P&L, and market values.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_portfolio_position",
            "description": "Add a new stock position to the user's portfolio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "shares": {"type": "number", "description": "Number of shares"},
                    "avg_price": {"type": "number", "description": "Average purchase price per share"}
                },
                "required": ["ticker", "shares", "avg_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_portfolio_position",
            "description": "Remove a position from the user's portfolio by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "position_id": {"type": "integer", "description": "The ID of the portfolio position to remove"}
                },
                "required": ["position_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_status",
            "description": "Check if major stock markets (US, Europe, Asia) are currently open or closed, with local times and trading hours.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist",
            "description": "Get the user's watchlist of tracked stocks (stocks they're interested in but haven't added to portfolio).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_watchlist",
            "description": "Add a stock to the user's watchlist to track it without adding to portfolio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "notes": {"type": "string", "description": "Optional notes about why this stock is being watched"}
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_watchlist",
            "description": "Remove a stock from the user's watchlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol to remove from watchlist"}
                },
                "required": ["ticker"]
            }
        }
    },
]

TOOL_HANDLERS = {
    "get_realtime_quote": lambda args: yahoo_service.get_realtime_quote(args["ticker"]),
    "get_historical_data": lambda args: yahoo_service.get_historical_data(
        args["ticker"], args.get("period", "1mo"), args.get("interval", "1d")
    ),
    "get_company_info": lambda args: yahoo_service.get_company_info(args["ticker"]),
    "get_financials": lambda args: yahoo_service.get_financials(args["ticker"]),
    "get_news": lambda args: yahoo_service.get_news(args["ticker"]),
    "get_recommendations": lambda args: yahoo_service.get_recommendations(args["ticker"]),
    "get_technical_indicators": lambda args: yahoo_service.get_technical_indicators(
        args["ticker"], args.get("period", "6mo")
    ),
    "compare_stocks": lambda args: yahoo_service.compare_stocks(args["tickers"]),
    "get_portfolio": lambda _: _get_portfolio_with_prices(),
    "add_portfolio_position": lambda args: database.add_position(
        args["ticker"], args["shares"], args["avg_price"]
    ),
    "remove_portfolio_position": lambda args: database.delete_position(args["position_id"]),
    "get_market_status": lambda _: yahoo_service.get_market_status(),
    "get_watchlist": lambda _: _get_watchlist_with_prices(),
    "add_to_watchlist": lambda args: database.add_watchlist_item(
        args["ticker"], args.get("notes", "")
    ),
    "remove_from_watchlist": lambda args: database.remove_watchlist_item(args["ticker"]),
}


def _get_portfolio_with_prices() -> dict:
    positions = database.get_portfolio()
    if not positions:
        return {"positions": [], "total_value": 0, "total_pnl": 0}
    enriched = yahoo_service.get_portfolio_summary(positions)
    total_value = sum(p.get("market_value", 0) for p in enriched if p.get("market_value"))
    total_cost = sum(p.get("cost_basis", 0) for p in enriched if p.get("cost_basis"))
    total_pnl = total_value - total_cost
    return {
        "positions": enriched,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_percent": round((total_pnl / total_cost * 100), 2) if total_cost else 0,
    }


def _get_watchlist_with_prices() -> dict:
    """Get watchlist enriched with current prices."""
    items = database.get_watchlist()
    if not items:
        return {"items": [], "count": 0}
    enriched = []
    for item in items:
        try:
            quote = yahoo_service.get_realtime_quote(item["ticker"])
            enriched.append({
                **item,
                "price": quote.get("price"),
                "change": quote.get("change"),
                "change_percent": quote.get("change_percent"),
            })
        except Exception:
            enriched.append({**item, "price": None, "error": "Failed to fetch price"})
    return {"items": enriched, "count": len(enriched)}


def _serialize_assistant_message(message) -> dict:
    """Serialize an assistant message, preserving extra fields like reasoning_content for thinking models."""
    # Use model_dump() to capture all fields including extras from model_extra
    dumped = message.model_dump() if hasattr(message, "model_dump") else {}

    msg = {"role": "assistant", "content": message.content}

    # Preserve reasoning_content for thinking models (e.g., kimi-k2.5)
    # The SDK returns it as "reasoning" in model_extra, but the API expects "reasoning_content"
    reasoning = dumped.get("reasoning") or getattr(message, "reasoning_content", None)
    if reasoning:
        msg["reasoning_content"] = reasoning

    # Preserve tool calls
    if message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]

    return msg


def _execute_tool(tool_name: str, arguments: dict) -> str:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = handler(arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool '{tool_name}' failed: {str(e)}"})


def _build_messages(session_id: str, user_message: str) -> list[dict]:
    """Build the message list from system prompt + chat history + new user message."""
    history = database.get_chat_history(session_id, limit=AGENT_CHAT_HISTORY_LIMIT)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages


def chat(session_id: str, user_message: str) -> str:
    """Process a user message and return the agent's response."""
    database.save_message(session_id, "user", user_message)

    messages = _build_messages(session_id, user_message)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=AGENT_TEMPERATURE,
    )

    choice = response.choices[0]

    iteration = 0
    while choice.finish_reason == "tool_calls" and iteration < AGENT_MAX_ITERATIONS:
        iteration += 1
        assistant_msg = choice.message
        messages.append(_serialize_assistant_message(assistant_msg))

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            result = _execute_tool(fn_name, fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=AGENT_TEMPERATURE,
        )
        choice = response.choices[0]

    reply = choice.message.content or "I wasn't able to generate a response. Please try again."

    database.save_message(session_id, "assistant", reply)

    return reply


def chat_stream(session_id: str, user_message: str):
    """Process a user message and yield SSE events as the response streams in."""
    database.save_message(session_id, "user", user_message)

    messages = _build_messages(session_id, user_message)

    full_reply = ""
    iteration = 0

    while iteration <= AGENT_MAX_ITERATIONS:
        # Check if this is a tool-calling iteration or the first call
        stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=AGENT_TEMPERATURE,
            stream=True,
        )

        # Collect the streamed response
        content_chunks = []
        reasoning_chunks = []
        tool_calls_data = {}  # index -> {id, name, arguments}
        finish_reason = None

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                if chunk.choices and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                continue

            # Accumulate reasoning_content for thinking models (e.g., kimi-k2.5)
            # The SDK stores it as "reasoning" in model_extra, not "reasoning_content"
            delta_dump = delta.model_dump() if hasattr(delta, "model_dump") else {}
            reasoning = delta_dump.get("reasoning") or getattr(delta, "reasoning_content", None)
            if reasoning:
                reasoning_chunks.append(reasoning)

            # Stream text content to client
            if delta.content:
                content_chunks.append(delta.content)
                yield f"data: {json.dumps({'type': 'content', 'text': delta.content})}\n\n"

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_data[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_data[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_data[idx]["arguments"] += tc.function.arguments

            if chunk.choices and chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

        content_so_far = "".join(content_chunks)

        # If we got tool calls, execute them and continue the loop
        if finish_reason == "tool_calls" and tool_calls_data:
            iteration += 1

            # Build assistant message with tool calls
            assistant_tool_calls = []
            for idx in sorted(tool_calls_data.keys()):
                tc = tool_calls_data[idx]
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })

            assistant_msg = {
                "role": "assistant",
                "content": content_so_far or None,
                "tool_calls": assistant_tool_calls,
            }
            # Preserve reasoning_content for thinking models
            reasoning_so_far = "".join(reasoning_chunks)
            if reasoning_so_far:
                assistant_msg["reasoning_content"] = reasoning_so_far
            reasoning_chunks = []
            messages.append(assistant_msg)

            # Execute each tool and send status events
            for tc_info in assistant_tool_calls:
                fn_name = tc_info["function"]["name"]
                yield f"data: {json.dumps({'type': 'tool_status', 'tool': fn_name, 'status': 'executing'})}\n\n"

                fn_args = json.loads(tc_info["function"]["arguments"])
                result = _execute_tool(fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_info["id"],
                    "content": result,
                })

                yield f"data: {json.dumps({'type': 'tool_status', 'tool': fn_name, 'status': 'done'})}\n\n"

            continue  # Next iteration will stream the follow-up response

        # No more tool calls — we're done
        full_reply = content_so_far
        break

    if not full_reply:
        full_reply = "I wasn't able to generate a response. Please try again."
        yield f"data: {json.dumps({'type': 'content', 'text': full_reply})}\n\n"

    database.save_message(session_id, "assistant", full_reply)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
