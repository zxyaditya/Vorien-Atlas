import os
import json
import requests
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter()

CACHE_DIR = os.path.join(os.path.dirname(__file__), "options_data_cache")
STATE_FILE = os.path.join(CACHE_DIR, "paper_portfolio_state.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "options_paper_daemon.log")

@router.get("/portfolio")
async def get_options_portfolio() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"status": "offline", "message": "Daemon not running or state file missing"}
    
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read state: {e}")
        
    open_pos = state.get("open_positions", {})
    inst_names = list(set([p["instrument_name"] for p in open_pos.values()]))
    
    live_prices = {}
    if inst_names:
        try:
            url = 'https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=ETH&kind=option'
            r = requests.get(url).json()
            data = r.get('result', [])
            for item in data:
                name = item['instrument_name']
                if name in inst_names:
                    ask = item.get('ask_price', 0)
                    mark = item.get('mark_price', 0)
                    live_prices[name] = ask if ask > 0 else mark
        except Exception:
            pass # fallback to open price if fetch fails
            
    total_unrealized = 0.0
    enriched_positions = []
    
    for tid, p in open_pos.items():
        name = p["instrument_name"]
        size = p["size"]
        open_price = p["open_price"]
        direction = p["direction"] # -1 for short
        
        current_price = live_prices.get(name, open_price)
        
        if direction == -1:
            pnl = (open_price - current_price) * size
        else:
            pnl = (current_price - open_price) * size
            
        total_unrealized += pnl
        
        enriched_positions.append({
            "trade_id": tid,
            "instrument": name,
            "size": size,
            "direction": "SELL" if direction == -1 else "BUY",
            "open_price": open_price,
            "current_price": current_price,
            "pnl": pnl,
            "dte": p.get("dte_at_open", 0),
            "greeks": p.get("greeks_at_open", {})
        })
        
    # Sort positions by PnL
    enriched_positions.sort(key=lambda x: x["pnl"], reverse=True)
        
    state["live_unrealized_pnl"] = total_unrealized
    state["enriched_positions"] = enriched_positions
    state["status"] = "online"
    
    return state

@router.get("/logs")
async def get_options_logs(lines: int = 100):
    if not os.path.exists(LOG_FILE):
        return {"logs": ["Log file not found."]}
        
    try:
        with open(LOG_FILE, "r") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:]
        return {"logs": [line.strip() for line in tail_lines]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {e}"]}
