"""
Tests for Layer 5 Paper Trading Execution Sandbox.
"""
import pytest
from paper_trading.contracts import PaperAccount, OpenPositionRequest
from paper_trading.engine import (
    _apply_slippage,
    compute_position_size,
    account_equity,
    open_position
)

def test_adverse_slippage_calculation():
    """Verify adverse slippage penalizes both long and short fills."""
    ref_price = 100.0
    slippage_bps = 10.0  # 10 bps = 0.1%
    
    # Long entry pays higher price (+0.1%)
    long_entry = _apply_slippage(ref_price, "long", slippage_bps, "entry")
    assert long_entry == pytest.approx(100.10)
    
    # Short entry pays lower price (-0.1%)
    short_entry = _apply_slippage(ref_price, "short", slippage_bps, "entry")
    assert short_entry == pytest.approx(99.90)

def test_position_sizing():
    """Position sizing must respect equity and allocation percentage."""
    equity = 100_000.0
    price = 2_000.0
    size_pct = 10.0  # $10,000 notional
    
    qty = compute_position_size(equity, price, size_pct)
    assert qty == pytest.approx(5.0)

def test_open_position_lifecycle():
    """Opening a position must deduct cash, apply slippage, and calculate initial position state."""
    account = PaperAccount(starting_balance=100_000.0, cash=100_000.0, fees_bps_per_side=5.0, slippage_bps=2.0).to_dict()
    open_positions = []
    
    req = OpenPositionRequest(
        account_id="acc_default",
        provider="synthetic",
        symbol="ETHUSDT",
        interval="1h",
        side="long",
        reference_price=3000.0,
        size_pct=10.0,
        stop_price=2800.0,
        take_profit_price=3400.0
    )
    
    pos, updated_acc = open_position(account, open_positions, req)
    
    assert pos.symbol == "ETHUSDT"
    assert pos.side == "long"
    assert pos.status == "open"
    assert pos.entry_price > 3000.0  # Slippage applied
    assert updated_acc["cash"] < 100_000.0  # Cash deducted
    assert pos.fees_paid > 0.0  # Entry fees charged

def test_mark_to_market_and_tp_sl():
    """Verify mark-to-market unrealized PnL and TP/SL hit checks."""
    from paper_trading.engine import mark_to_market, check_tp_sl_hit
    
    pos = {
        "side": "long",
        "quantity": 2.0,
        "entry_price": 100.0,
        "notional_at_entry": 200.0,
        "stop_price": 95.0,
        "take_profit_price": 110.0,
    }
    
    # MTM at 105.0 -> +$10 unrealized PnL
    mtm = mark_to_market(pos, 105.0)
    assert mtm["unrealized_pnl"] == 10.0
    assert mtm["unrealized_pnl_pct"] == 5.0
    
    # Hit stop loss on bar low = 94.0
    hit = check_tp_sl_hit(pos, high=102.0, low=94.0, close=96.0)
    assert hit == ("stop_loss", 95.0)
    
    # Hit take profit on bar high = 112.0
    hit_tp = check_tp_sl_hit(pos, high=112.0, low=101.0, close=108.0)
    assert hit_tp == ("take_profit", 110.0)

def test_close_position_lifecycle():
    """Closing a position must realize PnL and return capital to cash."""
    from paper_trading.engine import close_position
    
    account = PaperAccount(starting_balance=100_000.0, cash=90_000.0, fees_bps_per_side=5.0, slippage_bps=2.0).to_dict()
    pos = {
        "position_id": "pos_123",
        "symbol": "BTCUSDT",
        "side": "long",
        "quantity": 1.0,
        "entry_price": 50_000.0,
        "notional_at_entry": 50_000.0,
        "fees_paid": 25.0,
        "opened_at": "2024-01-01T00:00:00Z"
    }
    
    trade, updated_acc = close_position(account, pos, exit_price=55_000.0, exit_reason="take_profit")
    assert trade.realized_pnl > 4900.0  # ~$5000 profit minus fees
    assert updated_acc["cash"] > 140_000.0  # Initial cash + closed notional returned
