class AlphaMultiAsset:
    def __init__(self, symbols):
        self.symbols = symbols
        self.idx = 0
    def on_bar(self, bars, ts):
        # Simple deterministic round-robin pick
        symbol = self.symbols[self.idx % len(self.symbols)]
        self.idx += 1
        return {'alpha': 'alpha_4_multi_asset', 'signal': 'long', 'size': 1, 'symbol': symbol, 'ts': ts}
