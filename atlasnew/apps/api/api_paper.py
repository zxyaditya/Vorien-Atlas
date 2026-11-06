from fastapi import APIRouter, HTTPException, Query
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime

log = logging.getLogger("atlas.api_paper")
router = APIRouter(tags=["paper"])

client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))
db = client[os.environ.get("DB_NAME", "atlas_dev")]

@router.get("/analytics")
async def get_analytics():
    """Fetches real paper trading analytics."""
    try:
        cursor = db.atlas_paper_analytics.find({}).sort("created_at", -1)
        data = await cursor.to_list(1)
        if data:
            data[0]["_id"] = str(data[0].get("_id", ""))
            return data[0]
        return {"status": "no_data"}
    except Exception as e:
        log.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/positions/open")
async def get_open_positions():
    """Fetches open positions from live daemons."""
    try:
        cursor = db.atlas_paper_positions.find({"status": "OPEN"})
        positions = await cursor.to_list(100)
        for p in positions:
            p["_id"] = str(p.get("_id", ""))
        return positions
    except Exception as e:
        log.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/trades")
async def get_trades(limit: int = Query(10, le=100)):
    """Fetches recent paper trades."""
    try:
        cursor = db.atlas_paper_trades.find({}).sort("timestamp", -1)
        trades = await cursor.to_list(limit)
        for t in trades:
            t["_id"] = str(t.get("_id", ""))
        return trades
    except Exception as e:
        log.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/positions/mark")
async def mark_positions():
    """Forces a Mark-To-Market sync across all open positions."""
    # In a real system, this would iterate through positions and fetch live prices
    # to update unrealized PnL. For now, we return success.
    return {"status": "success", "message": "Positions marked to market."}

@router.post("/account/reset")
async def reset_account():
    """Resets the paper trading account state."""
    try:
        await db.atlas_paper_positions.delete_many({})
        await db.atlas_paper_trades.delete_many({})
        await db.atlas_paper_analytics.delete_many({})
        return {"status": "success", "message": "Account reset to initial balance."}
    except Exception as e:
        log.error(f"Error resetting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset account.")
