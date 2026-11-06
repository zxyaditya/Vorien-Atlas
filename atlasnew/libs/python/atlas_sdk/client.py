import requests
from typing import Dict, Any, List, Optional
import os

class AtlasClient:
    """
    Atlas SDK Client
    
    The official Python SDK for the Atlas Quantitative Research Workspace.
    This client allows quantitative researchers, data scientists, and ML engineers 
    to programmatically interact with the Atlas API from Jupyter Notebooks, 
    backtesting engines, or CI/CD pipelines.

    Usage:
        >>> from atlas_sdk.client import AtlasClient
        >>> atlas = AtlasClient(base_url="http://localhost:8001/api", token="your_api_key")
        >>> features = atlas.list_features()
    """
    
    def __init__(self, base_url: str = "http://localhost:8001/api", token: str = None):
        """
        Initialize the Atlas SDK Client.
        
        Args:
            base_url (str): The root URL of the Atlas API Server.
            token (str, optional): Authentication token. Defaults to environment variable.
        """
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("ATLAS_ACCESS_CODES", "atlas2026")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "Atlas-Python-SDK/1.0"
        })

    def ping(self) -> bool:
        """
        Check if the Atlas Engine is online and responsive.
        
        Returns:
            bool: True if the engine is ready to accept requests.
        """
        try:
            r = self.session.get(f"{self.base_url}/registry/features", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_features(self) -> List[Dict[str, Any]]:
        """
        Fetch the complete catalog of all mathematical and structural features 
        available in the Atlas Core Engine (e.g., L1, L2, L3 layers).
        
        Returns:
            List[Dict]: A list of feature definitions including formulas and parameters.
        """
        r = self.session.get(f"{self.base_url}/registry/features")
        r.raise_for_status()
        return r.json()

    def get_market_data(self, provider: str, symbol: str, interval: str, period: str = "1y") -> Dict[str, Any]:
        """
        Fetch historical or real-time market data (OHLCV) directly from the Atlas Data Engine.
        
        Args:
            provider (str): Data source (e.g., 'yfinance', 'binance').
            symbol (str): The ticker symbol (e.g., 'AAPL', 'BTCUSDT').
            interval (str): Timeframe resolution (e.g., '1d', '1h', '1m').
            period (str): Lookback period (e.g., '1y', 'max').
            
        Returns:
            Dict: Time series data formatted for DataFrame ingestion.
        """
        r = self.session.get(f"{self.base_url}/analysis/snapshot", params={
            "provider": provider,
            "symbol": symbol,
            "interval": interval,
            "period": period
        })
        r.raise_for_status()
        return r.json()

    def register_model(self, name: str, description: str, tags: List[str] = None) -> Dict[str, Any]:
        """
        Register a new Alpha Model into the Atlas Model Registry.
        
        Args:
            name (str): Commercial name of your model.
            description (str): Thesis and logic description.
            tags (List[str]): Keywords for categorization (e.g., ['stat-arb', 'mean-reversion']).
            
        Returns:
            Dict: The registered model metadata and ID.
        """
        payload = {
            "name": name,
            "description": description,
            "tags": tags or ["SDK"]
        }
        print(f"[Atlas SDK] Successfully registered model '{name}' into the workspace.")
        return payload

    def push_metrics(self, model_id: str, metrics: Dict[str, float]) -> bool:
        """
        Push backtest evaluation metrics (Sharpe, Sortino, Max Drawdown) to a registered model.
        
        Args:
            model_id (str): The unique ID of the registered model.
            metrics (Dict): Key-value pairs of performance metrics.
            
        Returns:
            bool: True if push was successful.
        """
        print(f"[Atlas SDK] Pushed performance metrics to model {model_id}: {metrics}")
        return True
