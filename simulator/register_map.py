"""
Modbus Holding Register Map
───────────────────────────
All addresses are 0-indexed (pymodbus style).
Documentation addresses = index + 40001.

float32  → 2 consecutive registers (big-endian IEEE 754)
uint32   → 2 consecutive registers (big-endian)
uint16   → 1 register
bool     → 1 register (0 or 1)
"""
import struct

# ── Register indices ──────────────────────────────────────────────────────────
# Line-level
R_LINE_STATE        = 0   # 40001 — uint16 (0=IDLE,1=RUNNING,2=MICROSTOP,3=STOPPED,4=FAULT,5=CHANGEOVER,6=CIP)
R_LINE_SPEED        = 1   # 40002–40003 — float32  bpm
R_GOOD_COUNT        = 3   # 40004–40005 — uint32   (monotonic)
R_REJECT_COUNT      = 5   # 40006–40007 — uint32   (monotonic)
R_ORDER_IDX         = 7   # 40008 — uint16  (0-based index into schedule, 0xFFFF=IDLE)
R_SKU_IDX           = 8   # 40009 — uint16  (0-based index, 0xFFFF=IDLE)
R_STOP_CODE         = 9   # 40010 — uint16  (0=none, see STOP_CODE_MAP)
R_FAULT_CODE        = 10  # 40011 — uint16  (0=none, 1=BD-M1, 2=BD-M2, 3=BD-M3)
R_ORDER_SEQ         = 11  # 40012 — uint16  sequential order number (1-based)
R_SIM_SPEED_X10     = 12  # 40013 — uint16  speed_factor × 10

# Infeed01
R_BOTTLE_PRESENCE   = 14  # 40015 — bool
R_INFEED_RATE       = 15  # 40016–40017 — float32  bpm
R_STARVED           = 17  # 40018 — bool
R_JAM_DETECTED      = 18  # 40019 — bool

# Filler01
R_TARGET_WEIGHT     = 20  # 40021–40022 — float32  g
R_ACTUAL_WEIGHT     = 22  # 40023–40024 — float32  g
R_FILL_TIME_MS      = 24  # 40025–40026 — uint32   ms
R_SCALE_STABLE      = 26  # 40027 — bool
R_DRIP_SENSOR       = 27  # 40028 — bool

# Capper01
R_TORQUE_TARGET     = 29  # 40030–40031 — float32  Ncm
R_TORQUE_ACTUAL     = 31  # 40032–40033 — float32  Ncm
R_TORQUE_IN_SPEC    = 33  # 40034 — bool
R_CAP_FEED_OK       = 34  # 40035 — bool

# Checkweigher01
R_GROSS_WEIGHT      = 36  # 40037–40038 — float32  g
R_WEIGHT_IN_SPEC    = 38  # 40039 — bool
R_REZERO_ACTIVE     = 39  # 40040 — bool

# Labeller01
R_LABEL_APPLIED     = 41  # 40042 — bool
R_LABEL_SENSOR_OK   = 42  # 40043 — bool
R_LABEL_STOCK       = 43  # 40044 — uint16 %

# Scanner01
R_BARCODE_OK        = 45  # 40046 — bool
R_RESCAN_COUNT      = 46  # 40047 — uint16

# Labeller02
R_HAZARD_REQUIRED   = 48  # 40049 — bool
R_HAZARD_APPLIED    = 49  # 40050 — bool
R_HAZARD_STOCK      = 50  # 40051 — uint16 %

# RejectPusher01
R_REJECT_TRIGGERED  = 52  # 40053 — bool
R_REJECT_REASON     = 53  # 40054 — uint16 (0=none,1=weight,2=torque,3=barcode,4=label,5=hazard_label)
R_PUSHER_CYCLE_MS   = 54  # 40055–40056 — uint32  ms

TOTAL_REGISTERS = 100

# ── State codes ───────────────────────────────────────────────────────────────
LINE_STATE = {
    "IDLE": 0, "RUNNING": 1, "MICROSTOP": 2,
    "STOPPED": 3, "FAULT": 4, "CHANGEOVER": 5, "CIP": 6,
}
LINE_STATE_INV = {v: k for k, v in LINE_STATE.items()}

# ── Stop code register values ─────────────────────────────────────────────────
STOP_CODE_MAP = {
    None: 0,
    "MS01": 1, "MS02": 2, "MS03": 3, "MS04": 4, "MS05": 5,
    "MS06": 6, "MS07": 7, "MS08": 8, "MS09": 9, "MS10": 10,
    "ST01": 11, "ST02": 12, "ST03": 13, "ST04": 14, "ST05": 15,
    "ST06": 16, "ST07": 17, "ST08": 18, "ST09": 19, "ST10": 20,
    "BD-M1": 21, "BD-M2": 22, "BD-M3": 23,
    "BD-MINOR-PE": 24, "BD-MINOR-LS": 25, "BD-MINOR-CA": 26,
}
STOP_CODE_MAP_INV = {v: k for k, v in STOP_CODE_MAP.items()}

REJECT_REASON_MAP = {
    None: 0, "weight": 1, "torque": 2, "barcode": 3,
    "label": 4, "hazard_label": 5,
}

# ── Pack/unpack helpers ───────────────────────────────────────────────────────
def pack_float32(value: float):
    """Return (high_word, low_word) for a float32."""
    b = struct.pack(">f", float(value))
    h, l = struct.unpack(">HH", b)
    return h, l

def unpack_float32(high: int, low: int) -> float:
    b = struct.pack(">HH", high, low)
    return struct.unpack(">f", b)[0]

def pack_uint32(value: int):
    """Return (high_word, low_word) for a uint32."""
    v = int(value) & 0xFFFFFFFF
    return (v >> 16) & 0xFFFF, v & 0xFFFF

def unpack_uint32(high: int, low: int) -> int:
    return (high << 16) | low

def bool_reg(value: bool) -> int:
    return 1 if value else 0
