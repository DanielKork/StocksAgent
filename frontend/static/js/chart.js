// TradingView Widget Integration

let chartWidgetCounter = 0;

function createChartContainer(ticker) {
    chartWidgetCounter++;
    const containerId = `tv-chart-${chartWidgetCounter}`;

    const wrapper = document.createElement('div');
    wrapper.className = 'chart-container';

    // Chart header with ticker and timeframe buttons
    const header = document.createElement('div');
    header.className = 'chart-header';
    header.innerHTML = `
        <span class="chart-header-ticker">📈 ${ticker}</span>
        <div class="chart-header-actions">
            <button class="chart-timeframe-btn" data-range="1D" data-container="${containerId}" data-ticker="${ticker}">1D</button>
            <button class="chart-timeframe-btn" data-range="5D" data-container="${containerId}" data-ticker="${ticker}">5D</button>
            <button class="chart-timeframe-btn active" data-range="1M" data-container="${containerId}" data-ticker="${ticker}">1M</button>
            <button class="chart-timeframe-btn" data-range="3M" data-container="${containerId}" data-ticker="${ticker}">3M</button>
            <button class="chart-timeframe-btn" data-range="1Y" data-container="${containerId}" data-ticker="${ticker}">1Y</button>
            <button class="chart-timeframe-btn" data-range="5Y" data-container="${containerId}" data-ticker="${ticker}">5Y</button>
        </div>
    `;

    // Chart widget container
    const chartDiv = document.createElement('div');
    chartDiv.className = 'chart-widget';
    chartDiv.id = containerId;

    wrapper.appendChild(header);
    wrapper.appendChild(chartDiv);

    // Add timeframe button listeners
    header.querySelectorAll('.chart-timeframe-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            header.querySelectorAll('.chart-timeframe-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Reload chart with new range
            loadTradingViewWidget(btn.dataset.ticker, btn.dataset.container, btn.dataset.range);
        });
    });

    // Load chart after a short delay (element needs to be in DOM)
    setTimeout(() => {
        loadTradingViewWidget(ticker, containerId, '1M');
    }, 100);

    return wrapper;
}

function loadTradingViewWidget(ticker, containerId, range) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear previous widget
    container.innerHTML = '';

    // Map our range to TradingView interval/range
    const rangeMap = {
        '1D': { interval: '5', range: '1D' },
        '5D': { interval: '15', range: '5D' },
        '1M': { interval: 'D', range: '1M' },
        '3M': { interval: 'D', range: '3M' },
        '1Y': { interval: 'W', range: '12M' },
        '5Y': { interval: 'M', range: '60M' },
    };

    const config = rangeMap[range] || rangeMap['1M'];
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';

    // Use TradingView's embeddable widget
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.textContent = JSON.stringify({
        autosize: true,
        symbol: ticker,
        interval: config.interval,
        range: config.range,
        timezone: "Etc/UTC",
        theme: theme,
        style: "1",
        locale: "en",
        allow_symbol_change: false,
        hide_top_toolbar: false,
        hide_legend: false,
        save_image: false,
        calendar: false,
        hide_volume: false,
        support_host: "https://www.tradingview.com",
    });

    const widgetDiv = document.createElement('div');
    widgetDiv.className = 'tradingview-widget-container';
    widgetDiv.style.height = '100%';
    widgetDiv.style.width = '100%';

    const innerDiv = document.createElement('div');
    innerDiv.className = 'tradingview-widget-container__widget';
    innerDiv.style.height = 'calc(100% - 32px)';
    innerDiv.style.width = '100%';

    widgetDiv.appendChild(innerDiv);
    widgetDiv.appendChild(script);
    container.appendChild(widgetDiv);
}
