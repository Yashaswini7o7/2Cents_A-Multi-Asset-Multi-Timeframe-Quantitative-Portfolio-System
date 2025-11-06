import uuid, json
from datetime import datetime
import math

class Fill:
    def __init__(self, order_id, symbol, side, size, price, ts, fee=0.0):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.size = float(size)
        self.price = float(price)
        self.ts = ts  # ISO string
        self.fee = float(fee)

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'size': self.size,
            'price': self.price,
            'ts': self.ts,
            'fee': self.fee
        }

class DeterministicExecutionModel:
    """
    Deterministic fill model that is fully driven by:
      - top_of_book_price
      - slippage_abs
      - slippage_pct
      - deterministic rounding by tick_size and lot_size
    Seeded randomness is supported but optional; seed must be provided and saved.
    """
    def __init__(self, slippage_abs=0.0, slippage_pct=0.0, tick_size=0.01, lot_size=1.0, seed=0):
        import numpy as _np, random as _random
        self._np = _np
        self._random = _random
        self.seed = seed
        self._np.random.seed(seed)
        self._random.seed(seed)
        self.slippage_abs = float(slippage_abs)
        self.slippage_pct = float(slippage_pct)
        self.tick_size = float(tick_size)
        self.lot_size = float(lot_size)

    def round_price(self, price):
        # round to nearest tick (deterministic)
        q = round(price / self.tick_size) * self.tick_size
        # protect against floating point residue
        return float(round(q, 8))

    def round_size(self, size):
        # round to lot
        q = math.floor(size / self.lot_size) * self.lot_size
        return float(q)

    def market_fill_price(self, top_price):
        # deterministic slippage model: top_price + slippage_abs + top_price*slippage_pct
        p = top_price + self.slippage_abs + top_price * self.slippage_pct
        return self.round_price(p)

    def fill_market(self, order_id, symbol, side, size, top_price, ts, fee_per_trade=0.0):
        price = self.market_fill_price(top_price)
        size_q = self.round_size(size)
        fee = float(fee_per_trade)
        fill = Fill(order_id, symbol, side, size_q, price, ts, fee=fee)
        return fill

    def snapshot(self):
        return {'seed': self.seed, 'slippage_abs': self.slippage_abs, 'slippage_pct': self.slippage_pct,
                'tick_size': self.tick_size, 'lot_size': self.lot_size}
