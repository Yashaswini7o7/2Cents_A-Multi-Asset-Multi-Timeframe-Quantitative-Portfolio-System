import logging, json, os
from datetime import datetime

def setup_logger(name="qr", level=logging.INFO):
    logger = logging.getLogger(name)
    if not logger.handlers:
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s.%(msecs)03dZ %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    logger.setLevel(level)
    return logger

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
