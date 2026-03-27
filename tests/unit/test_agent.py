import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_db_path(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.database.DATABASE_PATH", test_db)
    monkeypatch.setattr("backend.database._use_postgres", False)
    return test_db


@pytest.fixture
def init_test_db(mock_db_path):
    from backend.database import init_db
    init_db()


def test_execute_tool_known(init_test_db):
    from backend.agent import _execute_tool
    with patch("backend.yahoo_service.get_realtime_quote") as mock:
        mock.return_value = {"ticker": "AAPL", "price": 180.0}
        result = json.loads(_execute_tool("get_realtime_quote", {"ticker": "AAPL"}))
        assert result["ticker"] == "AAPL"
        assert result["price"] == 180.0


def test_execute_tool_unknown(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("nonexistent_tool", {}))
    assert "error" in result


def test_execute_tool_portfolio(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("get_portfolio", {}))
    assert "positions" in result
    assert result["positions"] == []


def test_execute_tool_add_position(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("add_portfolio_position", {"ticker": "AAPL", "shares": 10, "avg_price": 150.0}))
    assert result["ticker"] == "AAPL"


def test_execute_tool_error_handling(init_test_db):
    from backend.agent import _execute_tool
    with patch("backend.yahoo_service.get_realtime_quote") as mock:
        mock.side_effect = Exception("API down")
        result = json.loads(_execute_tool("get_realtime_quote", {"ticker": "AAPL"}))
        assert "error" in result


@patch("backend.agent.client")
def test_chat_basic(mock_openai, init_test_db):
    from backend.agent import chat

    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message.content = "Test response"
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    mock_openai.chat.completions.create.return_value = mock_response

    reply = chat("test_session", "Hello")
    assert reply == "Test response"


@patch("backend.agent.client")
def test_chat_with_tool_call(mock_openai, init_test_db):
    from backend.agent import chat

    # First response: tool call
    tool_choice = MagicMock()
    tool_choice.finish_reason = "tool_calls"
    tool_choice.message.role = "assistant"
    tool_choice.message.content = None
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "get_realtime_quote"
    tool_call.function.arguments = json.dumps({"ticker": "AAPL"})
    tool_choice.message.tool_calls = [tool_call]

    # Second response: final
    final_choice = MagicMock()
    final_choice.finish_reason = "stop"
    final_choice.message.content = "AAPL is at $180"
    final_choice.message.tool_calls = None

    mock_response_1 = MagicMock()
    mock_response_1.choices = [tool_choice]
    mock_response_1.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    mock_response_2 = MagicMock()
    mock_response_2.choices = [final_choice]
    mock_response_2.usage = MagicMock(prompt_tokens=20, completion_tokens=10)

    mock_openai.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

    with patch("backend.yahoo_service.get_realtime_quote") as mock_quote:
        mock_quote.return_value = {"ticker": "AAPL", "price": 180.0}
        reply = chat("test_session_tool", "What's AAPL?")
        assert "180" in reply


# Watchlist tool tests

def test_execute_tool_get_watchlist(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("get_watchlist", {}))
    assert "items" in result
    assert result["items"] == []


def test_execute_tool_add_to_watchlist(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("add_to_watchlist", {"ticker": "AAPL", "notes": "Watching for dip"}))
    assert result["ticker"] == "AAPL"


def test_execute_tool_remove_from_watchlist(init_test_db):
    from backend.agent import _execute_tool
    # First add, then remove
    _execute_tool("add_to_watchlist", {"ticker": "MSFT"})
    result = json.loads(_execute_tool("remove_from_watchlist", {"ticker": "MSFT"}))
    assert result is True


# Market status tool test

def test_execute_tool_market_status(init_test_db):
    from backend.agent import _execute_tool
    result = json.loads(_execute_tool("get_market_status", {}))
    assert "markets" in result
    assert "any_market_open" in result
    assert len(result["markets"]) == 3


# Database tests

def test_watchlist_crud(init_test_db):
    from backend.database import add_watchlist_item, get_watchlist, remove_watchlist_item

    # Add
    item = add_watchlist_item("TSLA", "Electric cars")
    assert item["ticker"] == "TSLA"

    # Get
    items = get_watchlist()
    assert len(items) == 1
    assert items[0]["ticker"] == "TSLA"

    # Remove
    removed = remove_watchlist_item("TSLA")
    assert removed is True

    # Verify empty
    items = get_watchlist()
    assert len(items) == 0


def test_watchlist_duplicate(init_test_db):
    from backend.database import add_watchlist_item

    add_watchlist_item("AAPL")
    with pytest.raises(ValueError, match="already in the watchlist"):
        add_watchlist_item("AAPL")
