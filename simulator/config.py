"""Load and expose configuration from config.yaml."""
import os
import yaml

_DEFAULT = {
    "simulator": {
        "instance_id": "sim01",
        "speed_factor": 60.0,
        "tick_hz": 10,
        "schedule_xlsx": "ISA95_Bottling_Line_Model_v1.xlsx",
    },
    "modbus": {"host": "0.0.0.0", "port": 502, "unit_id": 1},
    "enterprise": {
        "name": "Aerogen", "site": "Shannon",
        "area": "Bottling", "line": "Line01",
    },
    "production": {
        "microstop_mean_interval_s": 480,
        "base_reject_probability": 0.015,
        "label_stock_initial_pct": 95,
        "label_stock_depletion_per_1000": 3.0,
        "cap_stock_initial_pct": 98,
    },
    "logging": {
        "level": "INFO",
        "transactions_file": "logs/transactions.jsonl",
        "console": True,
    },
}

def _deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_config(path: str = "config.yaml") -> dict:
    cfg = dict(_DEFAULT)
    if os.path.exists(path):
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, user)
    return cfg
