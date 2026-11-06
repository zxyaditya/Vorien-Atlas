import React from "react";
import { useAtlas } from "../store/atlasStore";

/**
 * SymbolSelector — Reusable symbol dropdown populated from the backend's /api/market/symbols.
 *
 * Props:
 *   provider: string               — currently selected provider
 *   symbol: string                  — currently selected symbol
 *   onProviderChange: (v) => void   — called when provider changes
 *   onSymbolChange: (v) => void     — called when symbol changes
 *   showProvider?: boolean          — whether to show a provider dropdown (default true)
 *   style?: object                  — optional wrapper style
 */
export function SymbolSelector({
  provider, symbol, onProviderChange, onSymbolChange,
  showProvider = true, style,
}) {
  const { state } = useAtlas();
  const symbolsMap = state.symbols || {};

  const providers = Object.keys(symbolsMap).filter(k => Array.isArray(symbolsMap[k]) && symbolsMap[k].length > 0);
  const currentSymbols = symbolsMap[provider] || [];

  // When provider changes, auto-select first available symbol
  const handleProviderChange = (newProvider) => {
    onProviderChange(newProvider);
    const firstSymbol = (symbolsMap[newProvider] || [])[0];
    if (firstSymbol) {
      onSymbolChange(firstSymbol.symbol);
    }
  };

  return (
    <div style={{ display: "flex", gap: 10, ...style }}>
      {showProvider && (
        <div className="input-group" style={{ flex: 1 }}>
          <label className="input-label">Provider</label>
          <select
            className="input"
            value={provider}
            onChange={e => handleProviderChange(e.target.value)}
          >
            {providers.length === 0 ? (
              <>
                <option value="yahoo">Yahoo Finance</option>
                <option value="binance">Binance</option>
                <option value="synthetic">Synthetic</option>
                <option value="coingecko">CoinGecko</option>
              </>
            ) : (
              providers.map(p => (
                <option key={p} value={p}>
                  {p === "yahoo" ? "Yahoo Finance" : p === "coingecko" ? "CoinGecko" : p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))
            )}
          </select>
        </div>
      )}

      <div className="input-group" style={{ flex: 1 }}>
        <label className="input-label">Symbol</label>
        <select
          className="input"
          value={symbol}
          onChange={e => onSymbolChange(e.target.value)}
        >
          {currentSymbols.length === 0 ? (
            <option value={symbol}>{symbol}</option>
          ) : (
            currentSymbols.map(s => (
              <option key={s.symbol} value={s.symbol}>
                {s.symbol} — {s.name}
              </option>
            ))
          )}
        </select>
      </div>
    </div>
  );
}
