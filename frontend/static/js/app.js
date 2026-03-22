// StocksAgent — Main Application Logic

const API_BASE = '';
let sessionId = generateSessionId();
let isWaiting = false;

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
const toastContainer = document.getElementById('toastContainer');

// --- Initialization ---

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadPortfolio();
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

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
        });

        const data = await response.json();

        // Remove typing indicator
        typingEl.remove();
        isWaiting = false;

        if (data.error) {
            appendMessage('assistant', `⚠️ ${data.error}`);
        } else {
            appendMessage('assistant', data.reply);
        }

        // Refresh portfolio in case agent modified it
        loadPortfolio();

    } catch (error) {
        typingEl.remove();
        isWaiting = false;
        appendMessage('assistant', '⚠️ Failed to connect to the server. Make sure StocksAgent is running.');
    }
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
