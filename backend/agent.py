import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from backend import yahoo_service, database

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

SYSTEM_PROMPT = """You are StocksAgent — a knowledgeable, professional financial assistant powered by real-time Yahoo Finance data.

Your capabilities:
- Real-time stock quotes and price information
- Historical price data analysis
- Company profiles, financials (income statement, balance sheet, cash flow)
- News and analyst recommendations
- Technical analysis (RSI, MACD, moving averages, Bollinger Bands, ATR)
- Stock comparisons (side-by-side metrics)
- Portfolio tracking and P&L analysis

Guidelines:
1. Always use the provided tools to fetch live data — never make up prices or statistics.
2. Present numbers clearly: format large numbers (e.g., $1.5B market cap), use 2 decimal places for prices.
3. Use markdown formatting for readability: **bold** for key figures, tables for comparisons.
4. When showing a stock, include the ticker symbol so the UI can display a chart. Wrap tickers in double brackets like [[AAPL]] so the frontend can detect them and show a TradingView chart.
5. For technical analysis, explain what the indicators mean in plain language (e.g., "RSI of 75 suggests the stock is overbought").
6. Be concise but thorough. Don't repeat raw JSON — synthesize the data into a clear answer.
7. If a user asks about a topic you can answer from general finance knowledge (e.g., "what is P/E ratio?"), answer directly without calling tools.
8. For portfolio questions, use the portfolio tools to get current holdings and enrich with live data.
9. When comparing stocks, present data in a markdown table for easy reading.
10. Always be objective. Never give explicit buy/sell recommendations — present data and analysis and let the user decide.
11. If a tool call fails or returns an error, tell the user plainly and suggest alternatives.
"""

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


def _execute_tool(tool_name: str, arguments: dict) -> str:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = handler(arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool '{tool_name}' failed: {str(e)}"})


def chat(session_id: str, user_message: str) -> str:
    """Process a user message and return the agent's response."""
    database.save_message(session_id, "user", user_message)

    history = database.get_chat_history(session_id, limit=30)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.3,
    )

    choice = response.choices[0]

    max_iterations = 10
    iteration = 0
    while choice.finish_reason == "tool_calls" and iteration < max_iterations:
        iteration += 1
        assistant_msg = choice.message
        messages.append(assistant_msg)

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
            temperature=0.3,
        )
        choice = response.choices[0]

    reply = choice.message.content or "I wasn't able to generate a response. Please try again."

    database.save_message(session_id, "assistant", reply)

    return reply
