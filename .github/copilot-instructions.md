# StocksAgent — Project Guidelines

## Architecture

- **Backend**: Flask API (`backend/`) with SQLite/PostgreSQL, OpenAI-compatible function-calling agent, yfinance data service
- **Frontend**: Vanilla HTML/CSS/JS (`frontend/`) with TradingView charts, DOMPurify, marked.js, SSE streaming
- **Entry point**: `run.py` → `backend/app.py:main()`
- **Config**: All env vars loaded via `backend/config.py` from `.env` (python-dotenv) — **nothing is hardcoded**
- **Single-user mode**: No authentication
- **Database**: SQLite by default, PostgreSQL via `DATABASE_URL` env var

## Critical Patterns

### Agent Tool Handlers
- Every handler in `TOOL_HANDLERS` accepts `(args)` — lambda with args dict
- Never hardcode financial data — always fetch from Yahoo Finance via `backend/yahoo_service.py`
- System prompt loaded from file at `SYSTEM_PROMPT_PATH` (default: `backend/prompts/system_prompt.md`)
- API errors from upstream LLM provider are caught gracefully — never let raw 500s reach the user
- All agent behavior configurable: `AGENT_MAX_ITERATIONS`, `AGENT_TEMPERATURE`, `AGENT_CHAT_HISTORY_LIMIT`

### Database
- In tests, monkeypatch `backend.database.DATABASE_PATH` (NOT `backend.config.DATABASE_PATH`)
- Tables: `portfolio`, `chat_history`, `watchlist`
- Supports both SQLite (default) and PostgreSQL (`DATABASE_URL` env var)
- DB abstraction handles placeholder conversion (? → %s) automatically

### Frontend
- Sanitize with `DOMPurify.sanitize()` before DOM insertion
- No auth tokens — all API calls are simple fetch without Authorization headers
- Streaming via SSE (`/api/chat/stream`) with fallback to classic POST (`/api/chat`)

### Tools
Core: `get_realtime_quote`, `get_historical_data`, `get_company_info`, `get_financials`, `get_news`, `get_recommendations`, `get_technical_indicators`, `compare_stocks`
Market: `get_market_status`
Watchlist: `get_watchlist`, `add_to_watchlist`, `remove_from_watchlist`
Portfolio: `get_portfolio`, `add_portfolio_position`, `remove_portfolio_position`

### Cache Configuration
- All cache TTLs and sizes are configurable via env vars (`CACHE_QUOTE_TTL`, `CACHE_INFO_TTL`, etc.)
- Yahoo Finance retry logic configurable: `YAHOO_MAX_RETRIES`, `YAHOO_RETRY_DELAY`

## Build and Test

```bash
source venv/bin/activate
python run.py                         # Port 5001
python -m pytest tests/ -v            # Tests
```
