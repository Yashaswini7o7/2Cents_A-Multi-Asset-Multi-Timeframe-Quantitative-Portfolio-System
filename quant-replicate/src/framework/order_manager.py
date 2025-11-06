import uuid
import json
from framework.execution_model import DeterministicExecutionModel
from datetime import datetime

class OrderManager:
    """
    Accepts signals and creates deterministic orders + fills using DeterministicExecutionModel.
    Writes ndjson logs via provided writers (functions).
    """
    def __init__(self, exec_model: DeterministicExecutionModel, order_log_writer, fill_log_writer, fee_per_trade=0.0):
        self.exec_model = exec_model
        self.order_log_writer = order_log_writer
        self.fill_log_writer = fill_log_writer
        self.fee_per_trade = fee_per_trade
        self.orders = {}  # order_id -> order dict

    def submit_market_order(self, alpha_name, symbol, side, size, top_price, ts):
        order_id = str(uuid.uuid4())
        order = {
            'order_id': order_id,
            'alpha': alpha_name,
            'type': 'market',
            'symbol': symbol,
            'side': side,
            'size': float(size),
            'ts': ts
        }
        # log order
        self.order_log_writer(order)
        # deterministically produce fill
        fill = self.exec_model.fill_market(order_id, symbol, side, size, top_price, ts, fee_per_trade=self.fee_per_trade)
        self.fill_log_writer(fill.to_dict())
        self.orders[order_id] = {'order': order, 'fill': fill.to_dict()}
        return fill.to_dict()
