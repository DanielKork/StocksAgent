// StocksAgent — Main Application Logic

const API_BASE = '';
let sessionId = generateSessionId();
let isWaiting = false;
let useStreaming = true; // SSE streaming enabled by default

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const welcomeScreen = document.getElementById('welcomeScreen');
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggleSidebar');
const closeSidebarBtn = document.getElementById('closeSidebar');
const themeToggle = document.getElementById('themeToggle');
const newChatBtn = document.getElementById('newChatBtn');
const addPositionBtn = document.getElementById('addPositionBtn');
const addWatchlistBtn = document.getElementById('addWatchlistBtn');
const toastContainer = document.getElementById('toastContainer');

// --- Initialization ---

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadPortfolio();
    loadWatchlist();
    loadMarketStatus();
    loadTheme();
    chatInput.focus();
});

function setupEventListeners() {
    // Send message
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        sendBtn.disabled = !chatInput.value.trim();
    });

    // Quick actions
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', () => {
            const message = btn.dataset.message;
            chatInput.value = message;
            sendBtn.disabled = false;
            sendMessage();
        });
    });

    // Sidebar
    toggleSidebarBtn.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
    closeSidebarBtn.addEventListener('click', () => sidebar.classList.add('collapsed'));

    // Theme
    themeToggle.addEventListener('click', toggleTheme);

    // New chat
    newChatBtn.addEventListener('click', newChat);

    // Add position
    addPositionBtn.addEventListener('click', addPosition);

    // Add to watchlist
    if (addWatchlistBtn) {
        addWatchlistBtn.addEventListener('click', addToWatchlist);
    }
}

// --- Chat Functions ---

async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message || isWaiting) return;

    // Hide welcome screen
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }

    // Add user message
    appendMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Show typing indicator
    isWaiting = true;
    const typingEl = showTypingIndicator();

    if (useStreaming) {
        await sendMessageStreaming(message, typingEl);
    } else {
        await sendMessageClassic(message, typingEl);
    }

    // Refresh portfolio & watchlist in case agent modified them
    loadPortfolio();
    loadWatchlist();
}

async function sendMessageStreaming(message, typingEl) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000);
        const response = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
            signal: controller.signal,
        });

        if (!response.ok) {
            const errData = await response.json();
            typingEl.remove();
            isWaiting = false;
            appendMessage('assistant', `⚠️ ${errData.error || 'Request failed'}`);
            return;
        }

        // Remove typing indicator and create streaming message element
        typingEl.remove();
        const { contentEl } = createStreamingMessage();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6);
                if (!jsonStr) continue;

                try {
                    const event = JSON.parse(jsonStr);

                    if (event.type === 'content') {
                        fullContent += event.text;
                        const rawHtml = marked.parse(fullContent);
                        contentEl.innerHTML = DOMPurify.sanitize(rawHtml);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    } else if (event.type === 'tool_status') {
                        // Show tool execution status
                        if (event.status === 'executing') {
                            contentEl.innerHTML = `<div class="tool-status">🔧 Calling <strong>${DOMPurify.sanitize(event.tool)}</strong>...</div>`;
                        }
                    } else if (event.type === 'error') {
                        fullContent = `⚠️ ${event.text}`;
                        contentEl.innerHTML = DOMPurify.sanitize(marked.parse(fullContent));
                    } else if (event.type === 'done') {
                        // Detect ticker references and add charts
                        const tickerMatches = fullContent.match(/\[\[([A-Z]{1,10})\]\]/g);
                        if (tickerMatches) {
                            const tickers = [...new Set(tickerMatches.map(m => m.replace(/[\[\]]/g, '')))];
                            tickers.forEach(ticker => {
                                const chartDiv = createChartContainer(ticker);
                                contentEl.appendChild(chartDiv);
                            });
                        }
                    }
                } catch (e) {
                    // Skip invalid JSON
                }
            }
        }

        clearTimeout(timeoutId);
        isWaiting = false;

    } catch (error) {
        console.warn('Streaming failed, falling back to classic mode:', error);
        await sendMessageClassic(message, typingEl);
    }
}

async function sendMessageClassic(message, typingEl) {
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
        });

        const data = await response.json();

        typingEl.remove();
        isWaiting = false;

        if (data.error) {
            appendMessage('assistant', `⚠️ ${data.error}`);
        } else {
            appendMessage('assistant', data.reply);
        }

    } catch (error) {
        typingEl.remove();
        isWaiting = false;
        appendMessage('assistant', '⚠️ Failed to connect to the server. Make sure StocksAgent is running.');
    }
}

function createStreamingMessage() {
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';

    const avatarEl = document.createElement('div');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = 'S';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    messageEl.appendChild(avatarEl);
    messageEl.appendChild(contentEl);
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return { messageEl, contentEl };
}

function appendMessage(role, content) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatarEl = document.createElement('div');
    avatarEl.className = 'message-avatar';
    avatarEl.textContent = role === 'user' ? 'U' : 'S';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    if (role === 'assistant') {
        // Parse markdown
        const rawHtml = marked.parse(content);
        contentEl.innerHTML = DOMPurify.sanitize(rawHtml);

        // Detect ticker references like [[AAPL]] and render TradingView charts
        const tickerMatches = content.match(/\[\[([A-Z]{1,10})\]\]/g);
        if (tickerMatches) {
            const tickers = [...new Set(tickerMatches.map(m => m.replace(/[\[\]]/g, '')))];
            tickers.forEach(ticker => {
                const chartDiv = createChartContainer(ticker);
                contentEl.appendChild(chartDiv);
            });
        }
    } else {
        contentEl.textContent = content;
    }

    messageEl.appendChild(avatarEl);
    messageEl.appendChild(contentEl);
    chatMessages.appendChild(messageEl);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const el = document.createElement('div');
    el.className = 'typing-indicator';
    el.innerHTML = `
        <div class="message-avatar" style="background: linear-gradient(135deg, var(--accent), var(--green)); color: #fff; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700;">S</div>
        <div class="typing-dots">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return el;
}

// --- Portfolio Functions ---

async function loadPortfolio() {
    try {
        const res = await fetch(`${API_BASE}/api/portfolio`);
        const data = await res.json();
        renderPortfolio(data);
    } catch {
        // Silent fail — portfolio sidebar just shows empty
    }
}

function renderPortfolio(data) {
    const valueEl = document.getElementById('portfolioValue');
    const pnlEl = document.getElementById('portfolioPnl');
    const pnlLabelEl = document.getElementById('portfolioPnlLabel');
    const listEl = document.getElementById('positionsList');

    // Summary
    valueEl.textContent = formatCurrency(data.total_value || 0);

    const pnl = data.total_pnl || 0;
    const pnlPct = data.total_pnl_percent || 0;
    pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${formatCurrency(pnl)}`;
    pnlEl.className = `portfolio-pnl ${pnl >= 0 ? 'positive' : 'negative'}`;
    pnlLabelEl.textContent = `P&L: ${pnl >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`;

    // Positions
    if (!data.positions || data.positions.length === 0) {
        listEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📂</div>
                <div>No positions yet. Add stocks to your portfolio below.</div>
            </div>
        `;
        return;
    }

    listEl.innerHTML = data.positions.map(pos => `
        <div class="position-card">
            <div class="position-header">
                <span class="position-ticker">${escapeHtml(pos.ticker)}</span>
                <button class="position-delete" onclick="deletePosition(${pos.id})" title="Remove position">✕</button>
            </div>
            <div class="position-details">
                <span>Shares</span>
                <span class="position-detail-value">${pos.shares}</span>
                <span>Avg Cost</span>
                <span class="position-detail-value">${formatCurrency(pos.avg_price)}</span>
                <span>Current</span>
                <span class="position-detail-value">${pos.current_price ? formatCurrency(pos.current_price) : '—'}</span>
                <span>P&L</span>
                <span class="position-detail-value" style="color: ${pos.pnl >= 0 ? 'var(--green)' : 'var(--red)'}">
                    ${pos.pnl != null ? `${pos.pnl >= 0 ? '+' : ''}${formatCurrency(pos.pnl)} (${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent}%)` : '—'}
                </span>
                <span>Market Value</span>
                <span class="position-detail-value">${pos.market_value ? formatCurrency(pos.market_value) : '—'}</span>
            </div>
        </div>
    `).join('');
}

async function addPosition() {
    const ticker = document.getElementById('addTicker').value.trim().toUpperCase();
    const shares = parseFloat(document.getElementById('addShares').value);
    const avgPrice = parseFloat(document.getElementById('addPrice').value);

    if (!ticker) return showToast('Enter a ticker symbol', 'error');
    if (!shares || shares <= 0) return showToast('Enter valid number of shares', 'error');
    if (!avgPrice || avgPrice <= 0) return showToast('Enter valid average price', 'error');

    try {
        const res = await fetch(`${API_BASE}/api/portfolio`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, shares, avg_price: avgPrice }),
        });

        if (res.ok) {
            document.getElementById('addTicker').value = '';
            document.getElementById('addShares').value = '';
            document.getElementById('addPrice').value = '';
            showToast(`Added ${ticker} to portfolio`, 'success');
            loadPortfolio();
        } else {
            const data = await res.json();
            showToast(data.error || 'Failed to add position', 'error');
        }
    } catch {
        showToast('Failed to connect to server', 'error');
    }
}

async function deletePosition(id) {
    try {
        const res = await fetch(`${API_BASE}/api/portfolio/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Position removed', 'success');
            loadPortfolio();
        }
    } catch {
        showToast('Failed to remove position', 'error');
    }
}

// --- Theme ---

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('stocks-agent-theme', next);
}

function loadTheme() {
    const saved = localStorage.getItem('stocks-agent-theme');
    if (saved) {
        document.documentElement.setAttribute('data-theme', saved);
    }
}

// --- New Chat ---

function newChat() {
    sessionId = generateSessionId();
    chatMessages.innerHTML = '';
    if (welcomeScreen) {
        chatMessages.appendChild(welcomeScreen);
        welcomeScreen.style.display = '';
    }
    chatInput.focus();
}

// --- Utilities ---

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
}

function formatCurrency(value) {
    if (value == null) return '$0.00';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
    }).format(value);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// --- Watchlist Functions ---

async function loadWatchlist() {
    try {
        const res = await fetch(`${API_BASE}/api/watchlist`);
        const data = await res.json();
        renderWatchlist(data);
    } catch {
        // Silent fail
    }
}

function renderWatchlist(data) {
    const listEl = document.getElementById('watchlistItems');
    if (!listEl) return;

    if (!data.items || data.items.length === 0) {
        listEl.innerHTML = `
            <div class="empty-state" style="padding: 12px;">
                <div style="font-size: 12px; color: var(--text-muted);">No stocks in watchlist.</div>
            </div>
        `;
        return;
    }

    listEl.innerHTML = data.items.map(item => `
        <div class="watchlist-item">
            <div class="watchlist-item-info">
                <span class="watchlist-ticker">${escapeHtml(item.ticker)}</span>
                <span class="watchlist-price">${item.price ? formatCurrency(item.price) : '—'}</span>
            </div>
            <div class="watchlist-item-change">
                ${item.change_percent != null
                    ? `<span style="color: ${item.change_percent >= 0 ? 'var(--green)' : 'var(--red)'}">${item.change_percent >= 0 ? '+' : ''}${item.change_percent}%</span>`
                    : ''}
                <button class="watchlist-remove" onclick="removeFromWatchlist('${escapeHtml(item.ticker)}')" title="Remove">✕</button>
            </div>
        </div>
    `).join('');
}

async function addToWatchlist() {
    const input = document.getElementById('addWatchlistTicker');
    const ticker = input.value.trim().toUpperCase();
    if (!ticker) return showToast('Enter a ticker symbol', 'error');

    try {
        const res = await fetch(`${API_BASE}/api/watchlist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker }),
        });
        if (res.ok) {
            input.value = '';
            showToast(`Added ${ticker} to watchlist`, 'success');
            loadWatchlist();
        } else {
            const data = await res.json();
            showToast(data.error || 'Failed to add to watchlist', 'error');
        }
    } catch {
        showToast('Failed to connect to server', 'error');
    }
}

async function removeFromWatchlist(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/watchlist/${ticker}`, { method: 'DELETE' });
        if (res.ok) {
            showToast(`Removed ${ticker} from watchlist`, 'success');
            loadWatchlist();
        }
    } catch {
        showToast('Failed to remove from watchlist', 'error');
    }
}

// --- Market Status ---

async function loadMarketStatus() {
    const dot = document.getElementById('marketStatusDot');
    const text = document.getElementById('marketStatusText');
    if (!dot || !text) return;

    try {
        const res = await fetch(`${API_BASE}/api/market/status`);
        const data = await res.json();

        if (data.any_market_open) {
            dot.className = 'market-status-dot open';
            const openMarkets = data.markets.filter(m => m.is_open).map(m => m.market.split(' ')[0]);
            text.textContent = `Markets open: ${openMarkets.join(', ')}`;
        } else {
            dot.className = 'market-status-dot closed';
            text.textContent = 'All markets closed';
        }
    } catch {
        dot.className = 'market-status-dot closed';
        text.textContent = 'Market status unavailable';
    }

    // Refresh market status every 60 seconds
    setTimeout(loadMarketStatus, 60000);
}
