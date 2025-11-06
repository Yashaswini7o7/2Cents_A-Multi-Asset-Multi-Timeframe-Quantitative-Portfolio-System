import pandas as pd

class AlphaMTF:
    def __init__(self, symbol, fast=8, slow=34):
        self.symbol = symbol
        self.fast = fast; self.slow = slow
        self.minute_prices = []

    def on_bar_minute(self, bar, ts):
        self.minute_prices.append(bar['close'])
        if len(self.minute_prices) < self.slow:
            return None
        s = pd.Series(self.minute_prices)
        fast_ema = s.ewm(span=self.fast).mean().iloc[-1]
        slow_ema = s.ewm(span=self.slow).mean().iloc[-1]
        if fast_ema > slow_ema:
            return {'alpha': 'alpha_3_mtf', 'signal': 'long', 'size': 1, 'symbol': self.symbol, 'ts': ts}
        elif fast_ema < slow_ema:
            return {'alpha': 'alpha_3_mtf', 'signal': 'short', 'size': 1, 'symbol': self.symbol, 'ts': ts}
        return None
