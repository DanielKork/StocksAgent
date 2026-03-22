# StocksAgent — AI-Powered Finance Assistant

A conversational stock market agent that fetches real-time data from Yahoo Finance and answers any financial question using OpenAI GPT-4o with function calling. Features a sleek web UI with TradingView charts and portfolio tracking.

## Features

- **Real-time stock quotes** — Current price, change, volume, market cap, 52-week range
- **Company profiles** — Sector, industry, description, PE ratio, EPS, dividend yield
- **Financial statements** — Income statement, balance sheet, cash flow (annual + quarterly)
- **News & analyst recommendations** — Latest headlines, price targets, buy/sell ratings
- **Technical analysis** — RSI, MACD, SMA, EMA, Bollinger Bands, ATR with plain-language interpretation
- **Stock comparison** — Side-by-side metrics for multiple stocks in formatted tables
- **Portfolio tracking** — Add/remove positions, live P&L tracking, total portfolio value
- **TradingView charts** — Professional interactive charts embedded directly in chat
- **Dark/Light theme** — Toggle between dark and light modes
- **Chat history** — Conversation context maintained per session

## Tech Stack

- **Backend:** Python, Flask, OpenAI API (GPT-4o function calling), yfinance, ta (technical analysis)
- **Frontend:** HTML, CSS, JavaScript, TradingView widget, marked.js (markdown), DOMPurify
- **Database:** SQLite (portfolio + chat history)
- **Data Source:** Yahoo Finance (via yfinance library — no API key needed)

## Setup

### 1. Clone and navigate to the project

```bash
cd StocksAgent
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### 5. Run the application

```bash
python run.py
```

The app will start at **http://localhost:5000**

## Usage Examples

Ask the agent anything about stocks and finance:

| Question | What happens |
|---|---|
| "What's the price of AAPL?" | Fetches real-time quote, shows price + change + chart |
| "Compare TSLA, RIVN, and LCID" | Side-by-side comparison table of key metrics |
| "Show me technical analysis for NVDA" | RSI, MACD, moving averages with interpretation |
| "What are Apple's financials?" | Income statement, balance sheet, cash flow data |
| "Latest news for Microsoft" | Recent headlines with links |
| "What do analysts think about GOOGL?" | Price targets, recommendation ratings |
| "Add 10 shares of AAPL at $175 to my portfolio" | Adds position via agent tool |
| "How is my portfolio doing?" | Portfolio summary with live P&L |
| "What is a P/E ratio?" | General finance knowledge — answers without tools |

## Project Structure

```
StocksAgent/
├── run.py                          # Entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── backend/
│   ├── __init__.py
│   ├── config.py                   # Configuration loading
│   ├── database.py                 # SQLite schema & CRUD
│   ├── yahoo_service.py            # Yahoo Finance data service
│   ├── agent.py                    # OpenAI agent with function calling
│   └── app.py                      # Flask API & routes
├── frontend/
│   ├── index.html                  # Main chat UI
│   └── static/
│       ├── css/
│       │   └── style.css           # Dark/light theme styling
│       └── js/
│           ├── app.js              # Chat logic & API calls
│           └── chart.js            # TradingView widget integration
└── data/
    └── stocks_agent.db             # SQLite database (auto-created)
```

## How It Works

1. User sends a message via the web UI
2. Flask forwards it to the Agent (OpenAI GPT-4o with tool definitions)
3. GPT decides which tools to call (e.g., `get_realtime_quote`, `get_technical_indicators`)
4. Agent executes the tools via yfinance and feeds results back to GPT
5. GPT synthesizes a natural-language response with formatted data
6. Frontend renders the response with markdown formatting and TradingView charts
