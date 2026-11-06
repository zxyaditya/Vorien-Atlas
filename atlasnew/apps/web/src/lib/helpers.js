// Central API helper — reads from env, falls back to same-origin /api
import axios from 'axios';
export const BACKEND = process.env.REACT_APP_BACKEND_URL || "";
export const API = BACKEND ? `${BACKEND}/api` : "/api";
axios.defaults.headers.common['Authorization'] = 'Bearer atlas2026';

export function isAbortError(e) {
  if (!e) return false;
  return (
    e.name === "CanceledError" ||
    e.name === "AbortError" ||
    e.code === "ERR_CANCELED" ||
    e.message === "canceled" ||
    e.__CANCEL__ === true
  );
}

export function makeAbortable() {
  const ctrl = new AbortController();
  return { signal: ctrl.signal, abort: () => { try { ctrl.abort(); } catch {} } };
}

export function fmt(n, decimals = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtPct(n, decimals = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return (Number(n) * 100).toFixed(decimals) + "%";
}

export function fmtDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export function fmtRelative(d) {
  if (!d) return "—";
  const seconds = (Date.now() - new Date(d).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export const ASSETS = [
  "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
  "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "MATICUSDT",
];

export const ASSET_GROUPS = {
  Crypto: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
  Equities: ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"],
  Futures: ["BTC-PERP", "ETH-PERP", "SOL-PERP"]
};

export const INTERVALS = ["5m", "15m", "1h", "4h", "1d"];
