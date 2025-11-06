from framework.execution_model import DeterministicExecutionModel

def test_execution_model_repeatable():
    e1 = DeterministicExecutionModel(slippage_abs=0.0, slippage_pct=0.001, tick_size=0.01, lot_size=1.0, seed=42)
    p1 = e1.market_fill_price(100.0)
    e2 = DeterministicExecutionModel(slippage_abs=0.0, slippage_pct=0.001, tick_size=0.01, lot_size=1.0, seed=42)
    p2 = e2.market_fill_price(100.0)
    assert p1 == p2
