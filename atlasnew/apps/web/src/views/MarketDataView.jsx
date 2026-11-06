import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { createChart, CrosshairMode, LineStyle, CandlestickSeries, LineSeries } from "lightweight-charts";
import { API, fmt } from "../lib/helpers";
import { SymbolSelector } from "../components/SymbolSelector";

// ─── Color palettes for feature overlays ──────────────────────────────────
const OVERLAY_COLORS = [
  "hsl(222, 90%, 63%)",
  "hsl(155, 70%, 44%)",
  "hsl(40, 85%, 52%)",
  "hsl(258, 75%, 62%)",
  "hsl(0, 70%, 58%)",
];

export function MarketDataView() {
  const [provider, setProvider] = useState("yahoo");
  const [symbol, setSymbol] = useState("AAPL");
  const [interval, setIntervalVal] = useState("1d");
  const [period, setPeriod] = useState("1y");

  const [bars, setBars] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [servedBy, setServedBy] = useState(null);

  const [overlayFeatureId, setOverlayFeatureId] = useState("");
  const [overlayLoading, setOverlayLoading] = useState(false);
  const [activeOverlays, setActiveOverlays] = useState([]);

  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const overlaySeriesRefs = useRef([]);

  // ─── Initialize chart ─────────────────────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#000000" },
        textColor: "rgba(255,255,255,0.45)",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)", style: LineStyle.Dotted },
        horzLines: { color: "rgba(255,255,255,0.04)", style: LineStyle.Dotted },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(255,255,255,0.2)", style: LineStyle.Dashed, labelBackgroundColor: "#0C0F18" },
        horzLine: { color: "rgba(255,255,255,0.2)", style: LineStyle.Dashed, labelBackgroundColor: "#0C0F18" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.06)" },
      timeScale: {
        borderColor: "rgba(255,255,255,0.06)",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "hsl(155, 72%, 42%)",
      downColor: "hsl(355, 75%, 55%)",
      borderUpColor: "hsl(155, 72%, 42%)",
      borderDownColor: "hsl(355, 75%, 55%)",
      wickUpColor: "hsl(155, 60%, 35%)",
      wickDownColor: "hsl(355, 60%, 45%)",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const ro = new ResizeObserver(() => {
      if (!chartRef.current || !chartContainerRef.current) return;
      try {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      } catch (_) {}
    });
    ro.observe(chartContainerRef.current);

    return () => {
      ro.disconnect();
      chartRef.current = null;
      candleSeriesRef.current = null;
      overlaySeriesRefs.current = [];
      setTimeout(() => {
        try {
          chart.remove();
        } catch (_) {}
      }, 0);
    };
  }, []);

  // ─── Load OHLCV data ──────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true); setError(null); setSnapshot(null); setServedBy(null);
    try {
      const [ohlcvRes, snapRes] = await Promise.all([
        axios.get(`${API}/market/ohlcv`, { params: { provider, symbol, interval, period, limit: 500 } }),
        axios.get(`${API}/analysis/snapshot`, { params: { provider, symbol, interval, period } }).catch(() => ({ data: null })),
      ]);
      const data = ohlcvRes.data;
      setServedBy(data.served_by);
      const chartBars = data.bars.map(b => ({
        time: b.time.startsWith("20") ? b.time.split("T")[0] : b.time,
        open: b.open, high: b.high, low: b.low, close: b.close,
      }));
      setBars(chartBars);
      if (candleSeriesRef.current) {
        candleSeriesRef.current.setData(chartBars);
        chartRef.current?.timeScale().fitContent();
      }
      if (snapRes.data) setSnapshot(snapRes.data);
    } catch (err) {
      setError(err.response?.data?.detail ? (typeof err.response.data.detail === 'string' ? err.response.data.detail : JSON.stringify(err.response.data.detail)) : err.message);
    } finally { setLoading(false); }
  }, [provider, symbol, interval, period]);

  useEffect(() => { loadData(); }, [loadData]);

  // ─── Add feature overlay ──────────────────────────────────────────────
  const addOverlay = useCallback(async (featureId) => {
    if (!featureId || !chartRef.current) return;
    setOverlayLoading(true);
    try {
      const res = await axios.get(`${API}/features/values`, {
        params: { feature_id: featureId, provider, symbol, interval, period },
      });
      const colorIdx = overlaySeriesRefs.current.length % OVERLAY_COLORS.length;
      const color = OVERLAY_COLORS[colorIdx];
      const lineSeries = chartRef.current.addSeries(LineSeries, {
        color, lineWidth: 1.5,
        priceScaleId: "overlay-" + overlaySeriesRefs.current.length,
        title: featureId, lastValueVisible: true, priceLineVisible: false,
      });
      const lineData = res.data.points.filter(p => p.value !== null).map(p => ({
        time: p.time.split("T")[0], value: p.value,
      }));
      lineSeries.setData(lineData);
      overlaySeriesRefs.current.push({ id: featureId, series: lineSeries, color });
      setActiveOverlays(prev => [...prev, { id: featureId, color }]);
    } catch (err) {
      console.error("Overlay load failed:", err);
    } finally { setOverlayLoading(false); }
  }, [provider, symbol, interval, period]);

  const clearOverlays = useCallback(() => {
    overlaySeriesRefs.current.forEach(({ series }) => {
      try { chartRef.current?.removeSeries(series); } catch {}
    });
    overlaySeriesRefs.current = [];
    setActiveOverlays([]);
  }, []);

  const snap = snapshot?.snapshot || {};
  const regime = snap.regime_label || snap.regime || null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "12px 24px", borderBottom: "1px solid var(--border-dim)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 className="workspace-title" style={{ marginBottom: 0, marginRight: 4 }}>Market Data</h2>

          <SymbolSelector provider={provider} symbol={symbol} onProviderChange={setProvider} onSymbolChange={setSymbol} />

          <select className="input" value={interval} onChange={e => setIntervalVal(e.target.value)} style={{ width: 80 }}>
            {["1m","5m","15m","1h","4h","1d","1wk"].map(iv => <option key={iv} value={iv}>{iv}</option>)}
          </select>

          <select className="input" value={period} onChange={e => setPeriod(e.target.value)} style={{ width: 80 }}>
            {["1mo","3mo","6mo","1y","2y","5y"].map(p => <option key={p} value={p}>{p}</option>)}
          </select>

          <button className="btn btn-primary btn-sm" onClick={loadData} disabled={loading}>
            {loading ? "Loading…" : "Load"}
          </button>

          {servedBy && servedBy !== provider && (
            <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", padding: "2px 8px", background: "var(--amber-muted)", border: "1px solid var(--amber-border)", borderRadius: 3, color: "var(--amber)" }}>
              ⚠ served by {servedBy}
            </span>
          )}

          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            {activeOverlays.map(o => (
              <span key={o.id} style={{ fontSize: 10, fontFamily: "var(--font-mono)", padding: "2px 8px", background: "rgba(0,0,0,0.4)", border: `1px solid ${o.color}`, borderRadius: 3, color: o.color }}>
                {o.id}
              </span>
            ))}
            <input
              className="input" style={{ width: 200 }}
              placeholder="Feature ID overlay (Enter)"
              value={overlayFeatureId}
              onChange={e => setOverlayFeatureId(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && overlayFeatureId) { addOverlay(overlayFeatureId); setOverlayFeatureId(""); }}}
            />
            <button className="btn btn-secondary btn-sm" disabled={!overlayFeatureId || overlayLoading}
              onClick={() => { addOverlay(overlayFeatureId); setOverlayFeatureId(""); }}>
              {overlayLoading ? "…" : "+ Overlay"}
            </button>
            {activeOverlays.length > 0 && (
              <button className="btn btn-ghost btn-sm" onClick={clearOverlays}>Clear</button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div style={{ padding: "8px 24px", background: "var(--red-muted)", borderBottom: "1px solid var(--red-border)", fontSize: 12, color: "var(--red)", flexShrink: 0 }}>{error}</div>
      )}

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Chart */}
        <div style={{ flex: 1, position: "relative" }}>
          {loading && (
            <div style={{ position: "absolute", inset: 0, zIndex: 10, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.6)" }}>
              <div style={{ color: "var(--text-tertiary)", fontSize: 11, fontFamily: "var(--font-mono)" }}>Fetching market data…</div>
            </div>
          )}
          <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
        </div>

        {/* Stats sidebar */}
        {snapshot && (
          <div style={{ width: 240, flexShrink: 0, borderLeft: "1px solid var(--border-dim)", overflow: "auto", padding: "20px 16px", background: "var(--bg-surface)", display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", marginBottom: 4 }}>LAST CLOSE</div>
              <div style={{ fontSize: 22, fontWeight: 300, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>{fmt(snapshot.last_bar?.close)}</div>
              {regime && (
                <div style={{ marginTop: 8, display: "inline-block", padding: "2px 8px", fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.08em", border: "1px solid var(--border-base)", borderRadius: 3, color: "var(--text-secondary)" }}>
                  {regime}
                </div>
              )}
            </div>

            {snap.signals && Object.keys(snap.signals).length > 0 && (
              <div>
                <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 12 }}>Key Signals</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {Object.entries(snap.signals).slice(0, 10).map(([k, v]) => {
                    const val = typeof v === "number" ? v : (typeof v === "object" ? v?.value : v);
                    const valStr = typeof val === "number" ? (Math.abs(val) > 100 ? val.toFixed(1) : val.toFixed(4)) : String(val ?? "—");
                    const color = typeof val === "number" ? (val > 0 ? "var(--green)" : val < 0 ? "var(--red)" : "var(--text-secondary)") : "var(--text-secondary)";
                    return (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 10.5, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 120 }}>{k}</span>
                        <span style={{ fontSize: 10.5, color, fontFamily: "var(--font-mono)", flexShrink: 0 }}>{valStr}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {snapshot.explanation && (
              <div style={{ borderLeft: "2px solid var(--border-dim)", paddingLeft: 10 }}>
                <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 8 }}>Analysis</div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.65 }}>
                  {typeof snapshot.explanation === "object" ? (snapshot.explanation.pro || snapshot.explanation.beginner) : snapshot.explanation}
                </div>
              </div>
            )}

            <div style={{ borderTop: "1px solid var(--border-dim)", paddingTop: 10 }}>
              <div style={{ fontSize: 10, color: "var(--text-ghost)", fontFamily: "var(--font-mono)" }}>
                {bars.length} bars · {interval} · {period}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
