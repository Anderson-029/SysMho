// ── Autenticación ──────────────────────────────────────────
// Wrapper que inyecta X-API-Key en todas las peticiones /api/
async function apiFetch(url, options = {}) {
    const key = localStorage.getItem('sysmho_api_key') || '';
    const headers = { 'X-API-Key': key, ...(options.headers || {}) };
    return fetch(url, { ...options, headers });
}

async function unlockDashboard() {
    const key = document.getElementById('apiKeyInput').value;
    document.getElementById('lockError').style.display = 'none';
    try {
        const res = await fetch('/api/system/status', {
            headers: { 'X-API-Key': key }
        });
        if (res.ok) {
            localStorage.setItem('sysmho_api_key', key);
            document.getElementById('lockScreen').style.display = 'none';
            startLifecycles();
        } else {
            document.getElementById('lockError').style.display = 'block';
        }
    } catch (e) {
        // Servidor offline — guardar key y arrancar igual
        // (SysMho puede estar iniciando)
        localStorage.setItem('sysmho_api_key', key);
        document.getElementById('lockScreen').style.display = 'none';
        startLifecycles();
    }
}
// ─────────────────────────────────────────────────────────

const SYMBOLS = ["BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT", "POL-USDT"];
const charts = {};
const series = {};

// ── Estado global del sistema ──────────────────────────────────────────────
// true  = SysMho está vivo y respondiendo
// false = servidor caído o sin conexión → todos los pollers se pausan
let systemOnline = true;
let _offlineSince = null;  // timestamp cuando se detectó offline

function _setSystemOnline(online) {
    if (online === systemOnline) return; // sin cambio, no hacer nada
    systemOnline = online;

    const overlay = document.getElementById('offlineOverlay');
    if (!online) {
        _offlineSince = Date.now();
        if (overlay) overlay.style.display = 'flex';
        // Congelar cronómetro
        const el = document.getElementById('nextScanTime');
        const wrapper = document.getElementById('countdownWrapper');
        if (el) el.textContent = '--:--';
        if (wrapper) {
            wrapper.style.background = 'rgba(100,116,139,0.08)';
            wrapper.style.borderColor = 'rgba(100,116,139,0.2)';
        }
    } else {
        _offlineSince = null;
        if (overlay) overlay.style.display = 'none';
        // Refrescar datos inmediatamente al volver
        updateCharts();
        updateStats();
        pollSignals();
        pollPositions();
        updateHistory();
        pollTelemetry();
        fetchLastScanTime();
        updateAutonomyBadge();
    }
}
// ───────────────────────────────────────────────────────────────────────────

// Colores para las etiquetas
const SYMBOL_COLORS = {
    "BTC-USDT": "var(--btc-color)",
    "ETH-USDT": "var(--eth-color)",
    "BNB-USDT": "var(--bnb-color)",
    "SOL-USDT": "var(--sol-color)",
    "XRP-USDT": "var(--xrp-color)",
    "ADA-USDT": "var(--ada-color)",
    "AVAX-USDT": "var(--avax-color)",
    "LINK-USDT": "var(--link-color)",
    "DOT-USDT": "var(--dot-color)",
    "POL-USDT": "var(--matic-color)"
};

const SYMBOL_TEXT_COLORS = {
    "BTC-USDT": "#000",
    "BNB-USDT": "#000",
    "XRP-USDT": "#fff",
    "ADA-USDT": "#fff",
    "AVAX-USDT": "#fff",
    "LINK-USDT": "#fff",
    "DOT-USDT": "#fff",
    "POL-USDT": "#fff",
    "ETH-USDT": "#fff",
    "SOL-USDT": "#fff"
};

// Variables de Divisas
let exchangeRates = { USD: 1, COP: 3950, EUR: 0.92 };
let currentCurrency = 'USD';
let latestStats = null;

function changeCurrency() {
    currentCurrency = document.getElementById('currencySelector').value;
    if (latestStats) renderStats(latestStats);
}

function formatCurrency(value) {
    const rate = exchangeRates[currentCurrency] || 1;
    const converted = value * rate;

    let symbol = '$';
    if (currentCurrency === 'EUR') symbol = '€';
    if (currentCurrency === 'COP') symbol = 'COL ';

    const options = {
        minimumFractionDigits: currentCurrency === 'COP' ? 0 : 2,
        maximumFractionDigits: currentCurrency === 'COP' ? 0 : 2
    };

    return `${symbol}${converted.toLocaleString(undefined, options)}`;
}

function renderStats(sta) {
    latestStats = sta;
    if (sta.rates) exchangeRates = sta.rates;

    // 1. Balance Total
    document.getElementById('totalBalance').innerText = formatCurrency(sta.total_balance);

    // 2. PnL Diario (realizados hoy + flotante)
    const pnl = document.getElementById('globalPnl');
    const pnlValue = sta.pnl_diario !== undefined ? sta.pnl_diario : sta.pnl_global;
    pnl.innerText = (pnlValue >= 0 ? '+' : '') + formatCurrency(pnlValue);

    if (pnlValue > 0) {
        pnl.style.color = 'var(--success)';
        pnl.style.textShadow = '0 0 15px rgba(16, 185, 129, 0.5)';
    } else if (pnlValue < 0) {
        pnl.style.color = 'var(--danger)';
        pnl.style.textShadow = '0 0 15px rgba(239, 68, 68, 0.5)';
    } else {
        pnl.style.color = 'var(--text-muted)';
        pnl.style.textShadow = 'none';
    }

    // 3. Dinero en Juego
    document.getElementById('marginInUse').innerText = formatCurrency(sta.margin_in_use);

    // 4. Activos Vigilados (La reserva fue abstraída en Fase 6)
    document.getElementById('activeAssetsCount').innerText = `${SYMBOLS.length} Vigilando`;
}

function clearStats() {
    document.getElementById('totalBalance').innerText = '$0.00';
    const pnl = document.getElementById('globalPnl');
    pnl.innerText = '$0.00';
    pnl.style.color = 'var(--text-muted)';
    pnl.style.textShadow = 'none';
    document.getElementById('marginInUse').innerText = '$0.00';
    document.getElementById('activeAssetsCount').innerText = '0 Vigilando';
}

// Configuración Universal de Gráficos
function createChartConfig(containerId) {
    return {
        width: document.getElementById(containerId).clientWidth,
        height: 350,
        layout: {
            background: { type: 'solid', color: 'transparent' },
            textColor: '#94a3b8',
            fontFamily: 'JetBrains Mono',
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.02)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.02)' },
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: 'rgba(255, 255, 255, 0.05)' },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.05)',
            timeVisible: true
        },
    };
}

// Inicializar los gráficos dinámicamente
function initCharts() {
    const container = document.getElementById('chartsContainer');
    SYMBOLS.forEach(sym => {
        const shortSym = sym.split('-')[0];
        const chartDiv = document.createElement('div');
        chartDiv.className = 'glass-panel chart-wrapper';
        chartDiv.innerHTML = `
            <div class="chart-label">
                <div class="symbol-badge" style="background: ${SYMBOL_COLORS[sym]}; color: ${SYMBOL_TEXT_COLORS[sym]};">${shortSym}/USDT</div>
            </div>
            <div id="chart-${shortSym}" class="chart-id" style="height: 250px;"></div>
        `;
        container.appendChild(chartDiv);

        const chartId = `chart-${shortSym}`;
        const chart = LightweightCharts.createChart(document.getElementById(chartId), {
            ...createChartConfig(chartId),
            height: 250
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444'
        });

        charts[sym] = chart;
        series[sym] = candleSeries;
    });
    document.getElementById('activeAssetsCount').innerText = `${SYMBOLS.length} Vigilando`;
}

initCharts();

const chartsLoaded = {};
// Último precio conocido por símbolo — para detectar dirección entre pulsos
const lastKnownPrice = {};

function applyPriceLineColor(sym, currentClose) {
    if (currentClose == null) return;
    const prev = lastKnownPrice[sym];
    // En la carga inicial no hay "anterior" — usar neutro verde
    const isUp = prev == null ? true : currentClose >= prev;
    series[sym].applyOptions({
        priceLineColor: isUp ? '#10b981' : '#f43f5e',
        lastValueVisible: true,
    });
    lastKnownPrice[sym] = currentClose;
}

async function updateCharts() {
    if (!systemOnline) return;
    SYMBOLS.forEach(async (sym) => {
        try {
            if (!chartsLoaded[sym]) {
                // Carga inicial pesada (Historia 24h)
                const res = await apiFetch(`/api/market_data/${sym}?timeframe=5m&limit=288`);
                const data = await res.json();
                if (data && data.length > 0) {
                    series[sym].setData(data);
                    // Precio inicial: tomar el último close sin comparar (sin previo)
                    const last = data[data.length - 1];
                    lastKnownPrice[sym] = last.close;
                    series[sym].applyOptions({ priceLineColor: '#10b981', lastValueVisible: true });
                    chartsLoaded[sym] = true;
                }
            } else {
                // Pulso Táctico (Sólo última vela fluida)
                const res = await apiFetch(`/api/market_data/${sym}?timeframe=5m&limit=1`);
                const data = await res.json();
                if (data && data.length === 1) {
                    series[sym].update(data[0]);
                    // Comparar el close actual contra el último conocido
                    applyPriceLineColor(sym, data[0].close);
                }
            }
        } catch (e) {
            console.error(`Error actualizando ${sym}:`, e);
        }
    });
}

// Redimensionar gráficos al cambiar ventana
window.addEventListener('resize', () => {
    SYMBOLS.forEach(sym => {
        const shortSym = sym.split('-')[0];
        const containerId = `chart-${shortSym}`;
        charts[sym].resize(document.getElementById(containerId).clientWidth, 250);
    });
});

// Señales de IA
async function pollSignals() {
    if (!systemOnline) return;
    try {
        const res = await apiFetch('/api/pending_signals');
        if (!res.ok) throw new Error("Offline");
        const signals = await res.json();
        const container = document.getElementById('signalsContainer');

        // Actualizar cronómetro con el created_at más reciente de señales REGULAR
        const regularSignals = signals.filter(s => s.alert_category === 'REGULAR' && s.created_at);
        if (regularSignals.length > 0) {
            const latestTs = Math.max(...regularSignals.map(s => new Date(s.created_at).getTime() / 1000));
            if (!_lastScanTs || latestTs > _lastScanTs) {
                _lastScanTs = latestTs;
                _lastScanFetchTime = Date.now() / 1000;
                _nextScanIn = Math.max(0, 300 - (Date.now() / 1000 - latestTs));
            }
        }

        if (signals.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Sin amenazas u oportunidades detectadas.</div>`;
            return;
        }

        container.innerHTML = '';
        signals.forEach(s => {
            const card = document.createElement('div');
            card.className = 'signal-card';

            // Badge basado en alert_category (BOUNTY o REGULAR) — fuente única de verdad
            const category = s.alert_category || 'REGULAR';
            let badgeClass, badgeIcon, typeLabel;

            if (category === 'BOUNTY') {
                badgeClass = 'tb-premium';   // estilo dorado existente
                badgeIcon = '🏆';
                typeLabel = 'BOUNTY';
            } else {
                badgeClass = 'tb-standard';  // estilo neutro existente
                badgeIcon = '📡';
                typeLabel = 'REGULAR';
            }

            // --- HUD de Coherencia Triple ---
            const t5m = s.trend_5m || 'NEUTRAL';
            const t1h = s.trend_1h || 'NEUTRAL';
            const t4h = s.trend_4h || 'NEUTRAL';

            const getLedClass = (t) => {
                if (t === 'UP') return 'led-up';
                if (t === 'DOWN') return 'led-down';
                return 'led-neutral';
            };

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div class="tactical-badge ${badgeClass}">
                        <span>${badgeIcon}</span> ${typeLabel}
                    </div>
                    <div class="coherence-hud">
                        <div class="hud-item">
                            <span class="hud-label">4h</span>
                            <div class="led ${getLedClass(t4h)}"></div>
                        </div>
                        <div class="hud-item">
                            <span class="hud-label">1h</span>
                            <div class="led ${getLedClass(t1h)}"></div>
                        </div>
                        <div class="hud-item">
                            <span class="hud-label">5m</span>
                            <div class="led ${getLedClass(t5m)}"></div>
                        </div>
                    </div>
                </div>

                <div class="signal-header">
                    <span style="font-weight: 800; font-size: 1.1rem;">${s.symbol}</span>
                    <span class="signal-badge ${s.side.toLowerCase()}">${s.side}</span>
                </div>
                <div class="signal-stats">
                    <div class="s-box"><span>Capital a Usar</span><strong style="color: var(--secondary)">$${parseFloat(s.invested_usdt).toFixed(2)}</strong></div>
                    <div class="s-box"><span>IA Accuracy</span><strong style="color: #60a5fa">${(s.risk_score * 100).toFixed(1)}%</strong></div>
                    <div class="s-box"><span>Precio Unit.</span><strong>$${parseFloat(s.entry_price).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
                </div>

                <div class="projections">
                    ${s.exposure_warning ? `
                    <div style="grid-column: 1 / -1; background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); border-radius: 4px; padding: 6px; margin-bottom: 8px; color: var(--danger); font-size: 0.7rem; font-weight: 800; text-align: center; display: flex; align-items: center; justify-content: center; gap: 5px;">
                        <i class="fa-solid fa-triangle-exclamation"></i> EXPOSICIÓN > 50% DETECTADA
                    </div>
                    ` : ''}
                    <div class="p-item">
                        <span class="p-label">Prob. Éxito</span>
                        <span class="p-value p-win">${(s.win_probability * 100).toFixed(1)}%</span>
                    </div>
                    <div class="p-item">
                        <span class="p-label">Prob. Fracaso</span>
                        <span class="p-value p-loss">${(s.loss_probability * 100).toFixed(1)}%</span>
                    </div>
                    <div class="p-item">
                        <span class="p-label">Ganancia Est.</span>
                        <span class="p-value p-win">+$${parseFloat(s.potential_profit_usdt).toFixed(2)}</span>
                    </div>
                    <div class="p-item">
                        <span class="p-label">Pérdida Est.</span>
                        <span class="p-value p-loss">-$${parseFloat(s.potential_loss_usdt).toFixed(2)}</span>
                    </div>
                </div>

                <div class="signal-stats" style="margin-bottom: 1.25rem;">
                    <div class="s-box"><span>Objetivo TP</span><strong style="color: var(--success)">$${parseFloat(s.take_profit).toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong></div>
                    <div class="s-box"><span>Límite SL</span><strong style="color: var(--danger)">$${parseFloat(s.stop_loss).toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong></div>
                </div>

                <div class="actions">
                    <button class="btn btn-ok" onclick="resolve('${s.id}', 'approve')">Autorizar</button>
                    <button class="btn btn-no" onclick="resolve('${s.id}', 'reject')">Negar</button>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        const container = document.getElementById('signalsContainer');
        container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--danger); font-weight: 800;"><i class="fa-solid fa-power-off"></i> SISTEMA DESCONECTADO</div>`;
    }
}

async function dismissAllSignals() {
    if (confirm("¿Limpiar todo el panel de Auditoría? (Las señales se marcarán como ignoradas sin afectar la IA)")) {
        await apiFetch('/api/signals/dismiss_all', { method: 'POST' });
        pollSignals();
    }
}

async function resolve(id, action) {
    // Sincronización con las rutas reales del API (approve/reject)
    const route = action === 'approve' ? 'approve' : 'reject';
    await apiFetch(`/api/signals/${id}/${route}`, { method: 'POST' });

    // Refresco Inmediato
    pollSignals();
    updateHistory();

    if (action === 'approve') {
        console.log("⚡ [TACTICAL] Refresco agresivo activado...");
        // Disparamos un ciclo rápido de 5 segundos para captar la indexación
        let quickPolls = 0;
        const quickInterval = setInterval(() => {
            pollPositions();
            updateStats();
            quickPolls++;
            if (quickPolls >= 10) clearInterval(quickInterval);
        }, 500);
    }
}

async function closePosition(symbol, btn) {
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ CERRANDO...';
        btn.style.opacity = '0.6';
    }
    try {
        const encodedSymbol = symbol.replace('/', '-');
        const res = await apiFetch(`/api/positions/${encodedSymbol}/close`, { method: 'POST' });
        if (!res.ok) {
            // Reactivar botón para que el usuario pueda reintentar
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.textContent = 'CERRAR Y COBRAR (reintentar)';
            }
            return;
        }
        // Esperar 1.5s para que el trade quede registrado en BD antes de leer el resultado
        setTimeout(() => {
            pollPositions();
            updateStats();
            updateHistory();
            if (_autonomyPanelOpen) loadAutonomyPanel();
        }, 1500);
    } catch (e) {
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.textContent = 'CERRAR Y COBRAR (error red)';
        }
    }
}

// Telemetría
let hideMath = true;
function toggleSpam() {
    hideMath = !hideMath;
    const btn = document.getElementById('toggleMathSpam');
    btn.classList.toggle('active');
    pollTelemetry();
}

function clearLocalLogs() {
    document.getElementById('terminal-content').innerHTML = '';
}

async function pollTelemetry() {
    if (!systemOnline) return;
    try {
        // Reducimos limit a 60 para optimización (suficiente para el scroll)
        const res = await apiFetch('/api/logs?limit=60');
        if (!res.ok) throw new Error("API Offline");
        const data = await res.json();
        const term = document.getElementById('terminal-content');
        const atBottom = term.scrollHeight - term.clientHeight <= term.scrollTop + 30;

        if (!data.logs || data.logs.length === 0) {
            term.innerHTML = '<div class="log-line log-sys">📡 Esperando pulso neuronal...</div>';
            return;
        }

        term.innerHTML = '';
        data.logs.forEach(msg => {
            // Si el filtro está activo, omitimos ruido matemático repetitivo
            if (hideMath && (msg.includes('Analizando cálculo') || msg.includes('Base:') || msg.includes('Evolución'))) {
                return;
            }

            const p = document.createElement('div');
            p.className = 'log-line';

            let html = msg;

            // 1. Detección de Categoría Táctica
            if (msg.includes('CIRCUIT BREAKER') || msg.includes('🛑')) {
                p.classList.add('log-cb');
            }
            else if (msg.includes('Error') || msg.includes('❌') || msg.includes('FALLO') || msg.includes('RECHAZADA') || msg.includes('RECHAZADO')) {
                p.classList.add('log-err');
            }
            else if (msg.includes('AUTONOMÍA') || msg.includes('MetaScore') || msg.includes('SelfLearner') || msg.includes('🤖') || msg.includes('📈') || msg.includes('🖐')) {
                p.classList.add('log-auto');
            }
            else if (msg.includes('MANDO') || msg.includes('APROBADA') || msg.includes('ÉXITO') || msg.includes('APROBADO') || msg.includes('💸') || msg.includes('✅')) {
                p.classList.add('log-exec');
            }
            else if (msg.includes('CEREBRO') || msg.includes('🚀') || msg.includes('🛡️') || msg.includes('IGNICIÓN')) {
                p.classList.add('log-sys');
            }
            else if (msg.includes('Analizando') || msg.includes('velas')) {
                p.classList.add('log-math');
            } else {
                p.classList.add('log-brain');
            }

            // 2. Embellecimiento de Símbolos [BTC/USDT]
            html = html.replace(/\[([A-Z0-9/]+)\]/g, '<span class="log-symbol">[$1]</span>');

            // 3. Resaltado de Tiempo [HH:MM:SS]
            html = html.replace(/^\[(\d{2}:\d{2}:\d{2})\]/, '<span class="log-time">[$1]</span>');

            p.innerHTML = html;
            term.appendChild(p);
        });

        if (atBottom) term.scrollTop = term.scrollHeight;
    } catch (e) {
        console.error("Telemetry Error:", e);
        document.getElementById('terminal-content').innerHTML = `<div class="log-line log-err">❌ Error de Enlace: ${e.message}</div>`;
    }
}

let _prevPositionCount = null;

async function pollPositions() {
    if (!systemOnline) return;
    try {
        const res = await apiFetch('/api/positions');
        if (!res.ok) throw new Error("Offline");
        const positions = await res.json();
        const container = document.getElementById('positionsContainer');
        document.getElementById('posCount').innerText = `${positions.length} Activas`;

        // Detectar cierre automático (monitor cerró por TP/SL): refrescar historial y panel
        if (_prevPositionCount !== null && positions.length < _prevPositionCount) {
            setTimeout(() => {
                updateHistory();
                updateStats();
                if (_autonomyPanelOpen) loadAutonomyPanel();
            }, 1500);
        }
        _prevPositionCount = positions.length;

        if (positions.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">Sin posiciones activas.</div>`;
            const el = document.getElementById('totalNotional');
            if (el) el.innerText = formatCurrency(0);
            return;
        }

        const TAKER_FEE = 0.0004;

        // Formato de precio: 2 decimales para valores ≥ $1
        // Para sub-dólar: calcula los decimales mínimos para mostrar 2 cifras significativas
        const priceFmt = (v) => {
            if (!v) return '—';
            if (v >= 1) return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            // Sub-dólar: encuentra cuántos decimales necesita para tener 2 cifras significativas
            const dec = v < 0.001 ? 6 : v < 0.01 ? 5 : v < 0.1 ? 4 : 2;
            return v.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
        };
        const qtyFmt = (v) => {
            if (!v) return '—';
            if (v >= 1) return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
            return v.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 8 });
        };

        // Acumular totales para actualizar el NAV
        let totalNotionalSum = 0;

        container.innerHTML = '';
        positions.forEach(p => {
            const pnlGross = parseFloat(p.pnl_unrealized || 0);
            const invested  = parseFloat(p.invested_usdt || 0);   // notional en DB
            const leverage  = parseFloat(p.leverage || 1.0);
            const current   = parseFloat(p.current_price || p.entry_price || 0);
            const entry     = parseFloat(p.entry_price || 0);
            const tp        = parseFloat(p.take_profit || 0);
            const sl        = parseFloat(p.stop_loss || 0);
            const qty       = parseFloat(p.quantity || 0);
            const isLong    = p.side === 'BUY';

            // Margen real salido del wallet (colateral = notional ÷ apalancamiento)
            const margin    = leverage > 0 ? invested / leverage : invested;
            // Notional actual (valor total de la posición al precio de mercado)
            const notional  = qty > 0 ? qty * current : invested;

            totalNotionalSum += notional;

            // PnL neto estimado (descontando fee de cierre si cerráramos ahora)
            const closeFee  = current * qty * TAKER_FEE;
            const pnlNet    = pnlGross - closeFee;
            // ROI sobre margen (lo que muestra Binance)
            const roiPct    = margin > 0 ? (pnlNet / margin) * 100 : 0;
            const color     = pnlNet >= 0 ? 'var(--success)' : 'var(--danger)';

            // Punto de equilibrio (precio al que PnL neto = 0 tras ambas fees)
            const breakEven = isLong ? entry * (1 + 2 * TAKER_FEE) : entry * (1 - 2 * TAKER_FEE);
            const beDist    = current && breakEven ? ((current - breakEven) / breakEven * 100 * (isLong ? 1 : -1)) : null;

            // Distancias a TP y SL en %
            const distTP = tp && current ? ((tp - current) / current * 100 * (isLong ? 1 : -1)) : null;
            const distSL = sl && current ? ((current - sl) / current * 100 * (isLong ? 1 : -1)) : null;

            // Barra de progreso entre SL y TP
            // La fórmula (current-sl)/(tp-sl) da 0% en SL y 100% en TP
            // para LONG (sl<tp) y SELL (sl>tp) por igual — no invertir.
            let barPct = 50;
            if (tp && sl && current && tp !== sl) {
                barPct = Math.max(0, Math.min(100, ((current - sl) / (tp - sl)) * 100));
            }
            // Color basado en si el precio se movió favorable (verde) o desfavorable (rojo)
            // LONG: precio > entrada = favorable (verde), precio < entrada = desfavorable (rojo)
            // SHORT: precio < entrada = favorable (verde), precio > entrada = desfavorable (rojo)
            const isFavorable = isLong ? current > entry : current < entry;
            const barColor = isFavorable ? '#34d399' : '#ef4444';

            // Tiempo en posición
            let timeLabel = '';
            if (p.opened_at) {
                const mins = Math.floor((Date.now() - new Date(p.opened_at).getTime()) / 60000);
                timeLabel = mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`;
            }

            const card = document.createElement('div');
            card.className = 'signal-card';
            card.style.borderLeftColor = isLong ? 'var(--success)' : 'var(--danger)';
            card.innerHTML = `
                <div class="signal-header" style="margin-bottom:10px;">
                    <span style="font-weight:800; font-size:1.05rem;">${p.symbol}</span>
                    <div style="display:flex; gap:6px; align-items:center;">
                        ${timeLabel ? `<span style="font-size:0.65rem; color:var(--text-muted);">⏱ ${timeLabel}</span>` : ''}
                        <span class="signal-badge ${p.side.toLowerCase()}">${p.side} ${leverage}x</span>
                    </div>
                </div>

                <!-- PnL neto + ROI sobre margen -->
                <!-- PnL neto + ROI sobre margen -->
                <div style="text-align:center; margin-bottom:10px; padding:8px; background:rgba(255,255,255,0.04); border-radius:6px;">
                    <div style="font-size:0.6rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:3px;">PnL Neto Estimado</div>
                    <strong style="color:${color}; font-size:1.25rem;">${pnlNet >= 0 ? '+' : ''}$${pnlNet.toFixed(2)}</strong>
                    <span style="color:${color}; font-size:0.72rem; font-weight:700; margin-left:6px;">(${roiPct >= 0 ? '+' : ''}${roiPct.toFixed(2)}%)</span>
                    <div style="font-size:0.6rem; color:var(--text-muted); margin-top:2px;">
                        Bruto: ${pnlGross >= 0 ? '+' : ''}$${pnlGross.toFixed(2)} · Fee cierre: -$${closeFee.toFixed(2)}
                    </div>
                </div>

                <!-- Fila: Margen Utilizado (lo que salió del wallet) | Notional en Riesgo | Cantidad -->
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.4rem; font-size:0.72rem; margin-bottom:8px; text-align:center;">
                    <div style="background:rgba(255,255,255,0.03); border-radius:4px; padding:5px;">
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">Margen Utilizado</div>
                        <strong title="Capital de tu wallet en esta posición">$${margin.toFixed(2)}</strong>
                    </div>
                    <div style="background:rgba(255,255,255,0.03); border-radius:4px; padding:5px;">
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">En Riesgo</div>
                        <strong title="Valor actual de la posición (tokens × precio)">$${notional.toFixed(2)}</strong>
                    </div>
                    <div style="background:rgba(255,255,255,0.03); border-radius:4px; padding:5px;">
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">Cantidad</div>
                        <strong>${qtyFmt(qty)}</strong>
                    </div>
                </div>

                <!-- Fila: Entrada | Actual | Distancia al Punto de Equilibrio -->
                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.4rem; font-size:0.72rem; margin-bottom:8px; text-align:center;">
                    <div>
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">Entrada</div>
                        <strong>$${priceFmt(entry)}</strong>
                    </div>
                    <div>
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">Precio Actual</div>
                        <strong style="color:#60a5fa;">$${priceFmt(current)}</strong>
                    </div>
                    <div>
                        <div style="color:var(--text-muted); font-size:0.58rem; text-transform:uppercase;">A Equilibrio</div>
                        <strong style="color:#fbbf24;">$${priceFmt(breakEven)}</strong>
                        ${beDist !== null ? `<div style="font-size:0.58rem; color:${beDist >= 0 ? 'var(--success)' : 'var(--danger)'};">${beDist >= 0 ? '+' : ''}${beDist.toFixed(2)}%</div>` : ''}
                    </div>
                </div>

                <!-- Barra SL → Precio → TP -->
                <div style="margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.6rem; color:var(--text-muted); margin-bottom:3px;">
                        <span style="color:#ef4444;">SL $${priceFmt(sl)}</span>
                        <span style="color:#94a3b8;">posición en rango</span>
                        <span style="color:#34d399;">TP $${priceFmt(tp)}</span>
                    </div>
                    <div style="background:rgba(255,255,255,0.06); border-radius:4px; height:6px; overflow:hidden;">
                        <div style="height:100%; width:${barPct}%; background:${barColor}; border-radius:4px; transition:width 1s;"></div>
                    </div>
                </div>

                <div class="projections" style="margin-bottom:10px;">
                    <div class="p-item">
                        <span class="p-label">Objetivo TP</span>
                        <span class="p-value p-win">$${priceFmt(tp)}${distTP !== null ? ` <span style="font-size:0.65rem;">(${distTP > 0 ? '+' : ''}${distTP.toFixed(2)}%)</span>` : ''}</span>
                    </div>
                    <div class="p-item">
                        <span class="p-label">Stop Loss</span>
                        <span class="p-value p-loss">$${priceFmt(sl)}${distSL !== null ? ` <span style="font-size:0.65rem;">(${distSL > 0 ? '+' : ''}${distSL.toFixed(2)}%)</span>` : ''}</span>
                    </div>
                </div>

                <button class="btn btn-no" style="width:100%; padding:0.5rem; font-size:0.75rem; font-weight:800; text-transform:uppercase; letter-spacing:1px;" onclick="closePosition('${p.symbol}', this)">
                    CERRAR Y COBRAR <span style="color:${pnlNet >= 0 ? '#34d399' : '#ef4444'};">${pnlNet >= 0 ? '+' : ''}$${pnlNet.toFixed(2)}</span>
                </button>
            `;
            container.appendChild(card);
        });

        // Actualizar NAV: total notional de posiciones abiertas
        const totalNotionalEl = document.getElementById('totalNotional');
        if (totalNotionalEl) {
            totalNotionalEl.innerText = formatCurrency(totalNotionalSum);
        }
    } catch (e) {
        document.getElementById('positionsContainer').innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);"><i class="fa-solid fa-link-slash"></i> Sin Conexión al Motor</div>`;
        document.getElementById('posCount').innerText = `0 Activas`;
    }
}

async function updateHistory() {
    if (!systemOnline) return;
    try {
        // Obtener señales autorizadas Y trades cerrados en paralelo
        const [sigRes, tradeRes] = await Promise.all([
            apiFetch('/api/authorized_history'),
            apiFetch('/api/trades/history'),
        ]);
        const signals = sigRes.ok ? await sigRes.json() : [];
        const closedTrades = tradeRes.ok ? await tradeRes.json() : [];
        const container = document.getElementById('historyContainer');

        // Combinar en una lista unificada con tipo para renderizar diferente
        const items = [
            ...signals.map(s => ({ _type: 'signal', _time: new Date(s.resolved_at || s.created_at), ...s })),
            ...closedTrades.filter(t => t.status === 'CLOSED').map(t => ({
                _type: 'trade', _time: new Date(t.executed_at), ...t
            })),
        ].sort((a, b) => b._time - a._time).slice(0, 15);

        if (items.length === 0) {
            container.innerHTML = `<div style="text-align:center; color: var(--text-muted); padding:1rem;">Historial vacío.</div>`;
            return;
        }

        container.innerHTML = '';
        items.forEach(h => {
            const div = document.createElement('div');
            div.style = "padding: 8px; border-bottom: 1px solid var(--border); font-size: 0.75rem; display: flex; justify-content: space-between; align-items: center;";
            const timeStr = h._time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            if (h._type === 'trade') {
                // Trade cerrado: mostrar resultado real con PnL
                const pnl = parseFloat(h.pnl || 0);
                const won = pnl >= 0;
                const pnlColor = won ? 'var(--success)' : 'var(--danger)';
                const sideLabel = h.side === 'BUY' ? 'COMPRA' : 'VENTA';
                div.innerHTML = `
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:800;">${h.symbol}</span>
                        <span style="font-size:0.6rem; color:var(--text-muted);">${sideLabel} · cerrada</span>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:3px;">
                        <span style="font-weight:800; color:${pnlColor}; font-size:0.8rem;">${won ? '+' : ''}$${pnl.toFixed(2)}</span>
                        <span style="color:var(--text-muted); font-size:0.6rem;">${timeStr}</span>
                    </div>
                `;
            } else {
                // Señal: mostrar estado de aprobación
                const statusClass = h.status === 'EXECUTED' || h.status === 'APPROVED' ? 'buy'
                    : h.status === 'REJECTED' || h.status === 'FAILED' ? 'sell' : 'neutral';
                const statusEsp = {
                    'APPROVED': 'AUTORIZADA', 'EXECUTED': 'EJECUTADA',
                    'FAILED': 'FALLIDA', 'REJECTED': 'RECHAZADA', 'DISMISSED': 'IGNORADA'
                }[h.status] || h.status;
                const sideClass = h.side === 'BUY' ? 'color:var(--success)' : 'color:var(--danger)';
                const sideEsp = h.side === 'BUY' ? 'COMPRA' : 'VENTA';
                div.innerHTML = `
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:800;">${h.symbol}</span>
                        <span style="font-size:0.65rem; font-weight:700; ${sideClass}">${sideEsp}</span>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                        <span class="signal-badge ${statusClass}" style="font-size:0.6rem; padding:2px 6px;">${statusEsp}</span>
                        <span style="color:var(--text-muted); font-size:0.6rem;">${timeStr}</span>
                    </div>
                `;
            }
            container.appendChild(div);
        });
    } catch (e) { }
}

// Global Stats
async function updateStats() {
    if (!systemOnline) return;
    try {
        const res = await apiFetch('/api/stats');
        if (!res.ok) throw new Error("Offline");
        const sta = await res.json();
        renderStats(sta);
    } catch (e) {
        clearStats();
    }
}

async function injectTestSignal() {
    console.log("🧪 [STRESS TEST] Intentando inyectar señal...");
    const symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "POL/USDT"];
    const randomSymbol = symbols[Math.floor(Math.random() * symbols.length)];
    const side = Math.random() > 0.5 ? 'BUY' : 'SELL';

    try {
        const res = await apiFetch('/api/test/inject_signal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: randomSymbol, side: side })
        });
        const data = await res.json();
        if (data.status === 'injected') {
            console.log(`🧪 [STRESS TEST] Alerta inyectada: ${randomSymbol} ${side}`);
            pollSignals(); // Actualizar de inmediato
        } else {
            console.warn(`⚠️ [STRESS TEST] Rechazada: ${data.reason}`);
            alert(`Riesgo rechazado: ${data.reason}`);
        }
    } catch (e) {
        console.error('Error inyectando señal:', e);
        alert("Error de conexión al inyectar señal.");
    }
}

// Ignition
// El pulso se inicia mediante startLifecycles() al final del script
async function transferToReserve() {
    if (!confirm("¿Desea transferir todo el Capital Operativo a la Reserva del Exchange?")) return;
    try {
        const response = await apiFetch('/api/portfolio/transfer_to_reserve', { method: 'POST' });
        if (response.ok) {
            alert("✅ Capital reintegrado a la reserva.");
            updateStats();
            pollTelemetry(); // Refresco inmediato del log neuronal
        } else {
            const err = await response.json();
            alert(`❌ Error en la transferencia: ${err.detail}`);
        }
    } catch (e) { alert("❌ Error de comunicación en la transferencia."); }
}

async function showCapitalDialog() {
    const capital = prompt("Ingrese el nuevo Capital Total en Pesos Colombianos (COP):", "5000000");
    if (capital === null || capital === "") return;

    const amount = parseFloat(capital);
    if (isNaN(amount) || amount <= 0) {
        alert("Por favor ingrese un monto válido.");
        return;
    }

    try {
        const response = await apiFetch('/api/portfolio/adjust_capital', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ capital_cop: amount })
        });

        if (response.ok) {
            const res = await response.json();
            alert(`✅ Capital actualizado a $${res.new_usdt} USDT.`);
            updateStats(); // Refrescar indicadores
            pollTelemetry(); // Refresco inmediato del log neuronal
        } else {
            const err = await response.json();
            alert(`❌ Error: ${err.detail}`);
        }
    } catch (e) {
        alert(`❌ Error de conexión: ${e.message}`);
    }
}

async function checkSystemStatus() {
    try {
        const response = await apiFetch('/api/system/status');
        if (!response.ok) {
            if (response.status >= 500) {
                throw new Error("HTTP500");
            } else {
                throw new Error("HTTP_ERR_" + response.status);
            }
        }

        const data = await response.json();
        const statusEl = document.getElementById('apiLinkStatus');

        // Limpiar clases previas
        statusEl.className = 'api-status';

        if (data.api_link === 'ACTIVE') {
            statusEl.classList.add('api-active');
            statusEl.innerHTML = '<i class="fa-solid fa-link"></i> ENLACE ACTIVO';
            _setSystemOnline(true);
        } else if (data.api_link === 'RECONNECTING') {
            statusEl.classList.add('api-reconnecting');
            statusEl.innerHTML = '<i class="fa-solid fa-rotate"></i> RECONECTANDO...';
            _setSystemOnline(true); // el dashboard sigue operativo aunque Binance reconecte
        } else if (data.api_link === 'INVALID_KEYS') {
            statusEl.classList.add('api-disconnected');
            statusEl.innerHTML = '<i class="fa-solid fa-key"></i> LLAVES INVÁLIDAS';
            _setSystemOnline(true); // backend vivo aunque las keys fallen
        } else {
            statusEl.classList.add('api-disconnected');
            statusEl.innerHTML = '<i class="fa-solid fa-link-slash"></i> SIN ENLACE';
            _setSystemOnline(true);
        }
    } catch (e) {
        // Network error = SysMho apagado. HTTP500 = crash del motor.
        const statusEl = document.getElementById('apiLinkStatus');
        statusEl.className = 'api-status api-disconnected';

        if (e.message === "HTTP500") {
            statusEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> MOTOR CAÍDO';
        } else {
            statusEl.innerHTML = '<i class="fa-solid fa-power-off"></i> DESCONECTADO';
        }
        _setSystemOnline(false);
    }
}

async function checkDataFreshness() {
    if (!systemOnline) return;
    const el = document.getElementById('dataFreshness');
    try {
        const response = await apiFetch('/api/data/freshness');
        if (!response.ok) throw new Error("HTTP_ERR_" + response.status);

        const data = await response.json();
        el.className = 'api-status';
        const age = data.max_age_seconds || 0;
        const ageStr = age < 60 ? `${age}s` : `${Math.round(age / 60)}m`;

        if (data.status === 'FRESH') {
            el.classList.add('api-active');
            el.innerHTML = `<i class="fa-solid fa-clock"></i> DATOS ${ageStr}`;
        } else if (data.status === 'DELAYED') {
            el.classList.add('api-reconnecting');
            el.innerHTML = `<i class="fa-solid fa-clock"></i> DELAY ${ageStr}`;
        } else {
            el.classList.add('api-disconnected');
            el.innerHTML = `<i class="fa-solid fa-clock-rotate-left"></i> DATOS ${ageStr}`;
        }
        el.title = `Última vela 5m hace ${ageStr}`;
    } catch (e) {
        el.className = 'api-status api-disconnected';
        el.innerHTML = '<i class="fa-solid fa-clock"></i> SIN DATOS';
    }
}

async function checkDbStatus() {
    if (!systemOnline) return;
    const statusEl = document.getElementById('dbLinkStatus');
    try {
        const response = await apiFetch('/api/db/status');
        if (!response.ok) throw new Error("HTTP_ERR_" + response.status);

        const data = await response.json();
        statusEl.className = 'api-status';

        if (data.db_link === 'ACTIVE') {
            statusEl.classList.add('api-active');
            statusEl.innerHTML = '<i class="fa-solid fa-database"></i> BD ACTIVA';
        } else {
            statusEl.classList.add('api-disconnected');
            statusEl.innerHTML = '<i class="fa-solid fa-database"></i> BD CAÍDA';
        }
    } catch (e) {
        statusEl.className = 'api-status api-disconnected';
        statusEl.innerHTML = '<i class="fa-solid fa-database"></i> BD CAÍDA';
    }
}

// --- CRONÓMETRO DE PRÓXIMO SCAN (sincronizado con el motor real de SysMho) ---
let _lastScanTs = null;       // timestamp Unix del último scan real
let _nextScanIn = null;       // segundos restantes en el momento de la última consulta
let _lastScanFetchTime = null; // cuándo se hizo la última consulta al backend

async function fetchLastScanTime() {
    if (!systemOnline) return;
    try {
        const response = await apiFetch('/api/system/last_scan');
        if (!response.ok) return;
        const data = await response.json();
        if (data.last_scan_ts) {
            _lastScanTs = data.last_scan_ts;
            _lastScanFetchTime = Date.now() / 1000;
            _nextScanIn = data.next_scan_in;
        }
    } catch (e) { /* silencioso */ }
}

function updateScanCountdown() {
    const el = document.getElementById('countdownValue');
    const wrapper = document.getElementById('scanCountdown');
    if (!el || !wrapper) return;
    if (!systemOnline) return; // congelado — _setSystemOnline ya puso --:--

    let remaining = null;

    if (_lastScanTs && _lastScanFetchTime) {
        // Ajustar el tiempo restante según cuántos segundos han pasado desde la consulta
        const elapsed = (Date.now() / 1000) - _lastScanFetchTime;
        remaining = Math.max(0, (_nextScanIn ?? 300) - elapsed);
    }

    if (remaining === null) {
        el.textContent = 'ESPERA';
        wrapper.style.background = 'rgba(139,92,246,0.04)';
        return;
    }

    const m = Math.floor(remaining / 60);
    const s = Math.floor(remaining % 60);
    el.textContent = `${m}:${s.toString().padStart(2, '0')}`;

    // Flash morado intenso en los últimos 15s
    if (remaining <= 15) {
        wrapper.style.background = 'rgba(139,92,246,0.25)';
        wrapper.style.borderColor = 'rgba(139,92,246,0.7)';
    } else {
        wrapper.style.background = 'rgba(139,92,246,0.08)';
        wrapper.style.borderColor = 'rgba(139,92,246,0.25)';
    }

    // Cuando llega a 0 → pull inmediato de señales y refrescar timestamp
    if (remaining < 1) {
        pollSignals();
        fetchLastScanTime();
    }
}

// --- ESTADO DEL CEREBRO (AI Engine) ---
function updateEngineStatus() {
    const el = document.getElementById('engineStatus');
    if (!el) return;

    if (!systemOnline) {
        el.className = 'api-status api-disconnected';
        el.innerHTML = '<i class="fa-solid fa-brain"></i> CEREBRO OFFLINE';
        return;
    }

    if (!_lastScanTs) {
        el.className = 'api-status api-init';
        el.innerHTML = '<i class="fa-solid fa-brain fa-spin"></i> CEREBRO...';
        return;
    }

    const delta = (Date.now() / 1000) - _lastScanTs;

    if (delta < 360) {
        el.className = 'api-status api-active';
        el.innerHTML = '<i class="fa-solid fa-brain"></i> CEREBRO ACTIVO';
    } else if (delta < 900) {
        el.className = 'api-status api-reconnecting';
        el.innerHTML = '<i class="fa-solid fa-brain fa-beat"></i> RECONECTANDO';
    } else {
        el.className = 'api-status api-disconnected';
        el.innerHTML = '<i class="fa-solid fa-brain"></i> CEREBRO DETENIDO';
    }
}

// --- IGNICIÓN Y CICLOS DE VIDA ---
function startLifecycles() {
    console.log("🚀 SysMho: Iniciando ciclos de vida dinámicos...");

    // Carga Inicial
    updateCharts();
    updateStats();
    pollSignals();
    pollPositions();
    updateHistory();
    pollTelemetry();

    // Retrasamos el checkSystemStatus inicial para que la UI muestre
    // el proceso físico de "INICIANDO ENLACE..." por 3 segundos.

    // Intervalos Sincronizados (Overclock Extremo Mínimo Estable)
    setInterval(updateCharts, 2000);   // Gráficas cada 2s
    setInterval(updateStats, 2000);    // Balances y Reserva cada 2s
    setInterval(pollSignals, 5000);    // Predicciones cada 5s (CRITICAL FIX)
    setInterval(pollPositions, 2000);  // Posiciones cada 2s
    setInterval(updateHistory, 5000);  // Historial cada 5s
    setInterval(pollTelemetry, 2500);  // Terminal cada 2.5s
    setInterval(checkSystemStatus, 3000); // Estado enlace API (3s es ideal para evitar spamear)
    setInterval(checkDbStatus, 5000);      // Estado BD (5s, más estable)
    setInterval(checkDataFreshness, 10000); // Frescura de datos (10s)
    fetchLastScanTime();                      // Obtener último scan real al arrancar
    setInterval(fetchLastScanTime, 10000);   // Resincronizar cada 10s con el backend
    updateScanCountdown();                   // Arranque inmediato
    setInterval(updateScanCountdown, 1000);  // Cronómetro tick cada segundo

    // Cerebro (AI Engine)
    updateEngineStatus();
    setInterval(updateEngineStatus, 5000);  // Badge cerebro cada 5s

    // Autonomía
    updateAutonomyBadge();
    setInterval(updateAutonomyBadge, 10000); // Badge cada 10s

    // Sincronización de datos
    checkSyncStatus();
    setInterval(checkSyncStatus, 3000); // Verificar cada 3s al arrancar
}

// ────────────────────────────────────────────────────────────────────────────
//  PANEL DE AUTONOMÍA
// ────────────────────────────────────────────────────────────────────────────

let _autonomyPanelOpen = false;
let _autonomyRefreshTimer = null;

function toggleAutonomyPanel() {
    _autonomyPanelOpen = !_autonomyPanelOpen;
    const panel = document.getElementById('autonomyPanel');
    panel.style.display = _autonomyPanelOpen ? 'flex' : 'none';
    if (_autonomyPanelOpen) {
        loadAutonomyPanel();
        // Refrescar cada 5s mientras el panel está abierto
        _autonomyRefreshTimer = setInterval(loadAutonomyPanel, 5000);
    } else {
        clearInterval(_autonomyRefreshTimer);
        _autonomyRefreshTimer = null;
    }
}

async function checkSyncStatus() {
    if (!systemOnline) return;
    try {
        const res = await apiFetch('/api/system/sync_status');
        if (!res.ok) return;
        const data = await res.json();
        const badge = document.getElementById('syncBadge');
        const detail = document.getElementById('syncDetail');
        if (data.status === 'syncing') {
            badge.style.display = 'flex';
            badge.style.background = 'rgba(56,189,248,0.08)';
            badge.style.borderColor = 'rgba(56,189,248,0.25)';
            badge.style.color = '#38bdf8';
            detail.textContent = data.detail || 'SINCRONIZANDO...';
        } else {
            badge.style.display = 'none';
        }
    } catch (e) { /* silencioso */ }
}

async function updateAutonomyBadge() {
    if (!systemOnline) return;
    try {
        const res = await apiFetch('/api/autonomous/status');
        if (!res.ok) return;
        const data = await res.json();

        const badge = document.getElementById('autonomyBadge');
        const label = document.getElementById('autonomyLabel');
        const icon = badge.querySelector('i');
        const isAuto = data.autonomous_mode;

        if (isAuto) {
            badge.style.background = 'rgba(16,185,129,0.08)';
            badge.style.borderColor = 'rgba(16,185,129,0.25)';
            badge.style.color = '#34d399';
            icon.className = 'fa-solid fa-robot';
            label.textContent = 'AUTONOMÍA: ACTIVA';
            badge.title = 'El sistema opera y decide de forma autónoma';
        } else {
            badge.style.background = 'rgba(100,116,139,0.08)';
            badge.style.borderColor = 'rgba(100,116,139,0.2)';
            badge.style.color = '#94a3b8';
            icon.className = 'fa-solid fa-hand';
            label.textContent = 'AUTONOMÍA: NO ACTIVA';
            badge.title = 'Modo manual — se requiere aprobación humana';
        }
    } catch (e) { /* silencioso */ }
}

async function loadAutonomyPanel() {
    try {
        const [statusRes, decisionsRes] = await Promise.all([
            apiFetch('/api/autonomous/status'),
            apiFetch('/api/autonomous/decisions?limit=20'),
        ]);

        if (statusRes.ok) {
            const data = await statusRes.json();
            const isAuto = data.autonomous_mode;
            const cb = data.circuit_breaker || {};
            const ds = data.daily_stats || {};
            const learner = data.learner || {};

            document.getElementById('autonomyCurrentMode').textContent =
                isAuto ? '🤖 AUTÓNOMO' : '🖐 MANUAL';
            document.getElementById('autonomyCurrentMode').style.color =
                isAuto ? '#34d399' : '#94a3b8';

            const cbEl = document.getElementById('cbStatus');
            if (cb.triggered) {
                cbEl.innerHTML = `<span style="color:#fbbf24;">⚡ Circuit Breaker: ${cb.reason}</span>`;
            } else {
                cbEl.innerHTML = `<span style="color:#34d399;">✅ Circuit Breaker inactivo</span>`;
            }

            document.getElementById('autonTradesToday').textContent =
                `${ds.trades_today ?? 0} / ${cb.params?.max_daily_trades ?? '?'}`;
            const pnlPct = ds.daily_pnl_pct ?? 0;
            document.getElementById('autonDailyPnl').textContent = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`;
            document.getElementById('autonDailyPnl').style.color = pnlPct >= 0 ? '#34d399' : '#f43f5e';
            document.getElementById('autonConsecLosses').textContent =
                `${ds.consecutive_losses ?? 0} / ${cb.params?.max_consec_losses ?? '?'}`;

            const learnerEl = document.getElementById('learnerStats');
            learnerEl.innerHTML = [
                `Trades totales: <b style="color:#e6edf3">${learner.total_trades ?? 0}</b>`,
                `Win rate global: <b style="color:${(learner.global_win_rate ?? 0) >= 0.5 ? '#34d399' : '#f43f5e'}">${((learner.global_win_rate ?? 0) * 100).toFixed(1)}%</b>`,
                `Símbolos rastreados: <b style="color:#e6edf3">${learner.symbols_tracked ?? 0}</b>`,
                `Meta-modelo: <b style="color:${learner.meta_model_ready ? '#34d399' : '#64748b'}">${learner.meta_model_ready ? '✅ Disponible' : '⏳ Necesita 200+ trades'}</b>`,
            ].join('<br>');
        }

        if (decisionsRes.ok) {
            const ddata = await decisionsRes.json();
            const container = document.getElementById('autonomyDecisions');
            const decisions = ddata.decisions || [];

            if (decisions.length === 0) {
                container.innerHTML = '<div style="color:#64748b; font-size:0.7rem; text-align:center; padding:1rem;">Sin decisiones autónomas registradas todavía.</div>';
                return;
            }

            container.innerHTML = decisions.map(d => {
                const isApproved = d.decision === 'APPROVED';
                const borderColor = isApproved ? '#34d399' : '#f43f5e';
                const dirLabel = d.direction === 'BUY' ? 'COMPRA' : 'VENTA';
                const ts = d.created_at ? new Date(d.created_at).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) : '--';

                // Estado de la decisión
                let statusIcon, statusText;
                if (d.cb_active) {
                    statusIcon = '⚡'; statusText = 'BLOQUEADA POR SEGURIDAD';
                } else if (isApproved) {
                    statusIcon = '✅'; statusText = 'APROBADA — operación enviada';
                } else {
                    statusIcon = '🛑'; statusText = 'RECHAZADA — señal descartada';
                }

                // Razones del bot (array de strings ya en español)
                const reasons = Array.isArray(d.reasons) ? d.reasons : [];
                const reasonsHtml = reasons.length > 0
                    ? reasons.map(r => `<div style="color:#64748b; font-size:0.6rem;">· ${r}</div>`).join('')
                    : '';

                // Resultado real del trade (si ya cerró)
                let resultHtml = '';
                if (isApproved && d.trade_pnl != null) {
                    const pnl = parseFloat(d.trade_pnl);
                    const won = pnl >= 0;
                    resultHtml = `
                        <div style="margin-top:0.3rem; padding:3px 6px; background:${won ? 'rgba(52,211,153,0.08)' : 'rgba(244,63,94,0.08)'}; border-radius:3px; display:inline-block;">
                            <span style="color:${won ? '#34d399' : '#f43f5e'}; font-weight:700; font-size:0.65rem;">
                                ${won ? '💰 GANÓ' : '💸 PERDIÓ'} ${won ? '+' : ''}$${pnl.toFixed(2)}
                            </span>
                        </div>`;
                } else if (isApproved) {
                    resultHtml = `<div style="color:#64748b; font-size:0.6rem; margin-top:0.2rem;">⏳ trade aún abierto o pendiente</div>`;
                }

                return `
                    <div style="background:rgba(13,17,23,0.9); border:1px solid rgba(48,54,61,0.4); border-left:3px solid ${borderColor}; border-radius:5px; padding:0.5rem 0.65rem; font-size:0.68rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.2rem;">
                            <span style="color:#e6edf3; font-weight:700;">${d.symbol} · ${dirLabel}</span>
                            <span style="color:#64748b; font-size:0.62rem;">${ts}</span>
                        </div>
                        <div style="color:${borderColor}; font-weight:700; font-size:0.65rem; margin-bottom:0.2rem;">${statusIcon} ${statusText}</div>
                        ${reasonsHtml}
                        ${resultHtml}
                    </div>
                `;
            }).join('');
        }
    } catch (e) {
        console.error('Error cargando panel de autonomía:', e);
    }
}

async function resetCircuitBreaker() {
    const btn = document.getElementById('btnResetCB');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>&nbsp;REINICIANDO...';
    btn.style.opacity = '0.6';

    try {
        const res = await apiFetch('/api/autonomous/reset_cb', { method: 'POST' });
        if (res.ok) {
            btn.innerHTML = '<i class="fa-solid fa-check"></i>&nbsp;CONTADORES REINICIADOS';
            btn.style.background = 'rgba(16,185,129,0.1)';
            btn.style.borderColor = 'rgba(16,185,129,0.3)';
            btn.style.color = '#34d399';
            await loadAutonomyPanel();
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.background = 'rgba(251,191,36,0.06)';
                btn.style.borderColor = 'rgba(251,191,36,0.2)';
                btn.style.color = '#fbbf24';
                btn.disabled = false;
                btn.style.opacity = '1';
            }, 2000);
        }
    } catch (e) {
        btn.innerHTML = originalText;
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

async function resetDailyPnl() {
    try {
        const res = await apiFetch('/api/portfolio/reset_pnl', { method: 'POST' });
        if (res.ok) {
            const pnlEl = document.getElementById('globalPnl');
            pnlEl.style.transition = 'opacity 0.2s';
            pnlEl.style.opacity = '0.3';
            await updateStats();
            pnlEl.style.opacity = '1';
        }
    } catch (e) {
        console.error('Error resetting PnL:', e);
    }
}

async function setAutonomyMode(enable) {
    // Feedback visual inmediato en botones
    const btnAuto = document.querySelector('[onclick="setAutonomyMode(true)"]');
    const btnManual = document.querySelector('[onclick="setAutonomyMode(false)"]');
    if (btnAuto) { btnAuto.disabled = true; btnAuto.style.opacity = '0.5'; }
    if (btnManual) { btnManual.disabled = true; btnManual.style.opacity = '0.5'; }

    try {
        const res = await apiFetch(`/api/autonomous/toggle?enable=${enable}`, { method: 'POST' });
        if (res.ok) {
            await loadAutonomyPanel();
            await updateAutonomyBadge();
            // Cerrar modal tras 600ms para que se vea el cambio
            setTimeout(toggleAutonomyPanel, 600);
        }
    } catch (e) {
        console.error('Error cambiando modo de autonomía:', e);
    } finally {
        if (btnAuto) { btnAuto.disabled = false; btnAuto.style.opacity = '1'; }
        if (btnManual) { btnManual.disabled = false; btnManual.style.opacity = '1'; }
    }
}

// Al cargar: si hay key guardada, validar contra servidor
(function initAuth() {
    const savedKey = localStorage.getItem('sysmho_api_key');
    const lockScreen = document.getElementById('lockScreen');

    if (savedKey) {
        fetch('/api/system/status', { headers: { 'X-API-Key': savedKey } })
            .then(res => {
                if (res.ok) {
                    lockScreen.style.display = 'none';
                    startLifecycles();
                } else {
                    // Key inválida (cambiaron DASHBOARD_API_KEY) — forzar re-login
                    localStorage.removeItem('sysmho_api_key');
                    lockScreen.style.display = 'flex';
                }
            })
            .catch(() => {
                // Servidor offline al cargar — NO desbloquear
                // El usuario debe ver el lockScreen hasta que el servidor responda
                lockScreen.style.display = 'flex';
                const errorEl = document.getElementById('lockError');
                errorEl.textContent = 'Motor SysMho desconectado. Esperando...';
                errorEl.style.display = 'block';

                // Reintentar automáticamente cada 3 segundos
                setTimeout(initAuth, 3000);
            });
    } else {
        lockScreen.style.display = 'flex';
    }
})();
