import os
import requests
import logging
import threading
from typing import Dict, Any

logger = logging.getLogger("Broadcaster")

class WebhookBroadcaster:
    """
    Broadcasts paper trading decisions asynchronously via HTTP POST webhooks
    to support Copy Trading (e.g. Zignaly) or Custom Telegram Bots.
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        if not self.webhook_url:
            logger.warning("No webhook URL provided. Broadcaster will log payloads to console only.")

    def _send_payload(self, payload: Dict[str, Any]):
        """Runs in a background thread so we don't block the ML Inference loop."""
        if not self.webhook_url:
            logger.info(f"[SIMULATED WEBHOOK DISPATCH] {payload}")
            return
            
        try:
            # We use a short timeout because trading loops should never hang on slow webhooks
            response = requests.post(self.webhook_url, json=payload, timeout=5.0)
            if response.status_code in [200, 201]:
                logger.info(f"Successfully broadcasted signal. Status: {response.status_code}")
            else:
                logger.warning(f"Webhook returned unexpected status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to deliver webhook signal: {e}")

    def broadcast_trade(self, trade_info: Dict[str, Any], action: str, pnl: float = None):
        """
        Formats a generic trade payload. 
        `action` is either 'OPEN' or 'CLOSE'.
        `trade_info` contains instrument, size, direction, price.
        """
        payload = {
            "source": "Atlas Options Engine",
            "action": action,
            "instrument": trade_info.get("instrument_name", "UNKNOWN"),
            "underlying": trade_info.get("underlying", "ETH"),
            "type": trade_info.get("option_type", "unknown").upper(),
            "direction": "BUY" if trade_info.get("direction", 1) == 1 else "SELL",
            "size": trade_info.get("size", 0),
            "price": trade_info.get("price", 0.0),
            "timestamp": str(trade_info.get("timestamp", ""))
        }
        
        if action == "CLOSE" and pnl is not None:
            payload["pnl_percent"] = round(pnl * 100, 2)
            
        # Fire-and-forget
        thread = threading.Thread(target=self._send_payload, args=(payload,))
        thread.daemon = True
        thread.start()
