from fastapi import APIRouter
from atlas_core.compute import list_features

router = APIRouter(prefix="/api/v1/features", tags=["features"])

@router.get("/")
async def get_available_features():
    # Provide a structured fallback since internal features might not have clean metadata yet
    return {"features": [
        {"id": "log_return", "name": "Log Return", "description": "Logarithmic price return", "params": ["window"]},
        {"id": "rsi", "name": "RSI", "description": "Relative Strength Index", "params": ["window"]},
        {"id": "zscore", "name": "Rolling Z-Score", "description": "Z-Score of close price", "params": ["window"]},
        {"id": "macd", "name": "MACD", "description": "Moving Average Convergence Divergence", "params": ["fast", "slow", "signal"]},
        {"id": "atr", "name": "ATR", "description": "Average True Range", "params": ["window"]},
        {"id": "bbands", "name": "Bollinger Bands", "description": "Bollinger Bands Distance", "params": ["window", "std"]},
        {"id": "vol_ratio", "name": "Volume Ratio", "description": "Relative volume vs moving average", "params": ["window"]}
    ]}

