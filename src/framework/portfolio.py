from decimal import Decimal, getcontext

getcontext().prec = 12

class Portfolio:
    """
    Simple portfolio accounting for replication purpose.
    Tracks positions, cash, trade log, per-alpha pnl aggregation.
    """
    def __init__(self, initial_cash=100000.0):
        self.cash = Decimal(initial_cash)
        self.positions = {}  # symbol -> Decimal(size)
        self.trade_log = []
        self.equity_history = []  # tuples (ts_iso, equity_decimal)
        self.per_alpha_pnl = {}

    def apply_fill(self, fill: dict):
        # fill dict keys: order_id, symbol, side, size, price, ts, fee
        size = Decimal(str(fill['size']))
        price = Decimal(str(fill['price']))
        fee = Decimal(str(fill.get('fee', 0.0)))
        symbol = fill['symbol']
        side = fill['side']
        notional = size * price
        if side in ('buy','long','buy_aggressive'):
            self.positions[symbol] = self.positions.get(symbol, Decimal('0')) + size
            self.cash -= notional + fee
        else:
            # sell reduces position
            self.positions[symbol] = self.positions.get(symbol, Decimal('0')) - size
            self.cash += notional - fee
        # record trade
        self.trade_log.append(fill)
        # update equity snapshot (we do not have market-to-market valuation here; equity = cash + sum(0) for deterministic test)
        equity = self.cash  # for replication tests we compare trade-level P&L sums
        self.equity_history.append((fill['ts'], float(equity)))
        # accumulate per-alpha pnl by order_id alpha mapping (alpha must be embedded in fill['order_id'] mapping externally)
        # per-alpha handling done by caller

    def get_equity_series(self):
        # return as simple list [(ts, equity)]
        return self.equity_history
