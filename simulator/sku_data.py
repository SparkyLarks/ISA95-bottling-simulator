"""
SKU and Liquid Base definitions — mirrors Material_Defs sheet.
Single source of truth for simulator parameters.
"""
from dataclasses import dataclass, field
from typing import Optional

FILL_RATE_ML_PER_SEC = 120.0   # configurable global fill rate


@dataclass
class LiquidBase:
    base_id: str
    name: str
    density_g_ml: float
    carbonated: bool
    cip_after_orders: int        # 4 for still, 0 means always after liquid change


@dataclass
class SKU:
    sku_id: str
    name: str
    liquid_base_id: str
    volume_ml: float
    torque_target_ncm: float
    hazard_flag: bool
    market: str
    label_group: str
    nominal_speed_bpm: float
    work_master_id: str

    @property
    def target_weight_g(self) -> float:
        base = LIQUID_BASES[self.liquid_base_id]
        return self.volume_ml * base.density_g_ml

    @property
    def fill_time_s(self) -> float:
        return self.volume_ml / FILL_RATE_ML_PER_SEC

    @property
    def fill_time_ms(self) -> int:
        return int(self.fill_time_s * 1000)


LIQUID_BASES: dict[str, LiquidBase] = {
    "BASE-LEM": LiquidBase("BASE-LEM", "Lemon Base",       1.01, False, 4),
    "BASE-DL":  LiquidBase("BASE-DL",  "Diet Lemon Base",  1.02, False, 4),
    "BASE-COL": LiquidBase("BASE-COL", "Cola Base",        1.04, True,  0),
    "BASE-DC":  LiquidBase("BASE-DC",  "Diet Cola Base",   1.02, True,  0),
}

SKUS: dict[str, SKU] = {
    "LEM-200-IE": SKU("LEM-200-IE", "Lemon 200mL",         "BASE-LEM", 200,  32, False, "IE", "LBL-A", 120, "WM-001"),
    "LEM-500-IE": SKU("LEM-500-IE", "Lemon 500mL",         "BASE-LEM", 500,  34, False, "IE", "LBL-A", 100, "WM-002"),
    "LEM-2L-IE":  SKU("LEM-2L-IE",  "Lemon 2L",            "BASE-LEM", 2000, 36, False, "IE", "LBL-A",  60, "WM-003"),
    "LEM-6L-IE":  SKU("LEM-6L-IE",  "Lemon 6L",            "BASE-LEM", 6000, 40, False, "IE", "LBL-A",  30, "WM-004"),
    "DL-200-IE":  SKU("DL-200-IE",  "Diet Lemon 200mL",    "BASE-DL",  200,  32, False, "IE", "LBL-B", 120, "WM-001"),
    "DL-500-IE":  SKU("DL-500-IE",  "Diet Lemon 500mL",    "BASE-DL",  500,  34, False, "IE", "LBL-B", 100, "WM-002"),
    "COL-500-IE": SKU("COL-500-IE", "Cola 500mL",          "BASE-COL", 500,  34, False, "IE", "LBL-C",  95, "WM-005"),
    "COL-2L-IE":  SKU("COL-2L-IE",  "Cola 2L",             "BASE-COL", 2000, 36, False, "IE", "LBL-C",  55, "WM-005"),
    "DC-500-IE":  SKU("DC-500-IE",  "Diet Cola 500mL IE",  "BASE-DC",  500,  34, True,  "IE", "LBL-D",  95, "WM-006"),
    "DC-500-UK":  SKU("DC-500-UK",  "Diet Cola 500mL UK",  "BASE-DC",  500,  34, True,  "UK", "LBL-E",  95, "WM-006"),
}

SKU_LIST = list(SKUS.keys())   # index → sku_id

def get_sku(sku_id: str) -> Optional[SKU]:
    return SKUS.get(sku_id)

def sku_index(sku_id: str) -> int:
    try:
        return SKU_LIST.index(sku_id)
    except ValueError:
        return 0xFFFF

def sku_from_index(idx: int) -> Optional[SKU]:
    if idx == 0xFFFF or idx >= len(SKU_LIST):
        return None
    return SKUS[SKU_LIST[idx]]
