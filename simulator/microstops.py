"""
Microstop Definitions — MS01 through MS10
──────────────────────────────────────────
Each microstop has:
  - code, name, duration range (sim seconds)
  - weight (relative probability of selection)
  - fingerprint_fn: returns the signal fingerprint dict
  - signal_mutations: which registers to perturb during the stop
"""
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from .register_map import (
    R_SCALE_STABLE, R_DRIP_SENSOR, R_CAP_FEED_OK,
    R_REZERO_ACTIVE, R_LABEL_SENSOR_OK, R_BARCODE_OK,
    R_RESCAN_COUNT, R_BOTTLE_PRESENCE, R_STARVED,
)


@dataclass
class Microstop:
    code: str
    name: str
    station: str
    duration_lo_s: float       # sim seconds
    duration_hi_s: float
    weight: float              # relative selection probability
    fingerprint_fn: Callable   # () → dict of signal name→value
    # Register mutations applied while stop is active: index→value
    mutations_fn: Callable     # (registers) → None


def _ms01_fp():
    return {
        "bottle_presence": random.choice([0, 0, 1]),
        "infeed_rate_drop_pct": round(random.uniform(30, 60), 1),
        "fill_cycle_start": False,
    }
def _ms01_mut(regs):
    regs[R_BOTTLE_PRESENCE] = random.choice([0, 0, 0, 1])
    regs[R_STARVED] = 0

def _ms02_fp():
    delta = round(random.uniform(150, 950), 0)
    return {"scale_stable": False, "fill_time_delta_ms": delta}
def _ms02_mut(regs):
    regs[R_SCALE_STABLE] = 0

def _ms03_fp():
    return {"drip_sensor": True, "post_fill_delay_ms": random.randint(300, 800)}
def _ms03_mut(regs):
    regs[R_DRIP_SENSOR] = 1

def _ms04_fp():
    return {"cap_feed_ok": False, "torque_missing_cycles": random.randint(1, 3)}
def _ms04_mut(regs):
    regs[R_CAP_FEED_OK] = 0

def _ms05_fp():
    oor_delta = round(random.uniform(1.5, 4.5), 2)
    return {"torque_oor_delta_ncm": oor_delta, "torque_recheck": True}
def _ms05_mut(regs):
    pass  # torque signals already fluctuating in normal sim

def _ms06_fp():
    return {"rezero_active": True, "weight_drift_g": round(random.uniform(0.5, 2.5), 2)}
def _ms06_mut(regs):
    regs[R_REZERO_ACTIVE] = 1

def _ms07_fp():
    return {"label_sensor_ok": False, "label_peelback_count": random.randint(1, 3)}
def _ms07_mut(regs):
    regs[R_LABEL_SENSOR_OK] = 0

def _ms08_fp():
    rescans = random.randint(1, 3)
    return {"barcode_read_ok": False, "rescan_count": rescans}
def _ms08_mut(regs):
    regs[R_BARCODE_OK] = 0
    regs[R_RESCAN_COUNT] = random.randint(1, 3)

def _ms09_fp():
    slow_ms = random.randint(900, 2000)
    return {"pusher_cycle_time_ms": slow_ms, "threshold_ms": 800}
def _ms09_mut(regs):
    pass  # pusher cycle time will be elevated in line simulation

def _ms10_fp():
    return {"outfeed_near_full": True, "speed_dip_bpm": round(random.uniform(5, 20), 1)}
def _ms10_mut(regs):
    pass  # line speed dip handled in line sim


MICROSTOPS: list[Microstop] = [
    Microstop("MS01", "Infeed Misfeed",          "Infeed01",      6,  25, weight=12, fingerprint_fn=_ms01_fp, mutations_fn=_ms01_mut),
    Microstop("MS02", "Fill Stabilisation Wait", "Filler01",      8,  40, weight=18, fingerprint_fn=_ms02_fp, mutations_fn=_ms02_mut),
    Microstop("MS03", "Nozzle Drip Detect",      "Filler01",      5,  20, weight=8,  fingerprint_fn=_ms03_fp, mutations_fn=_ms03_mut),
    Microstop("MS04", "Cap Feed Stutter",        "Capper01",     10,  50, weight=10, fingerprint_fn=_ms04_fp, mutations_fn=_ms04_mut),
    Microstop("MS05", "Torque Recheck",          "Capper01",     12,  60, weight=9,  fingerprint_fn=_ms05_fp, mutations_fn=_ms05_mut),
    Microstop("MS06", "Checkweigher Re-zero",    "Checkweigher01",10, 90, weight=11, fingerprint_fn=_ms06_fp, mutations_fn=_ms06_mut),
    Microstop("MS07", "Label Peelback",          "Labeller01",    8,  45, weight=10, fingerprint_fn=_ms07_fp, mutations_fn=_ms07_mut),
    Microstop("MS08", "Barcode Re-scan",         "Scanner01",     5,  30, weight=9,  fingerprint_fn=_ms08_fp, mutations_fn=_ms08_mut),
    Microstop("MS09", "Reject Pusher Slow Return","RejectPusher01",8, 35, weight=7,  fingerprint_fn=_ms09_fp, mutations_fn=_ms09_mut),
    Microstop("MS10", "Outfeed Accumulation Nudge","Line01",      15, 120,weight=6,  fingerprint_fn=_ms10_fp, mutations_fn=_ms10_mut),
]

_WEIGHTS = [m.weight for m in MICROSTOPS]
_MS_BY_CODE = {m.code: m for m in MICROSTOPS}


def pick_microstop(sku_id: str = None) -> Microstop:
    """Pick a random microstop, biased by weights.
    Large-volume SKUs get higher MS02 weight."""
    weights = list(_WEIGHTS)
    if sku_id in ("LEM-2L-IE", "LEM-6L-IE", "COL-2L-IE"):
        # Large volume → more fill stabilisation issues
        weights[1] *= 1.8   # MS02
    return random.choices(MICROSTOPS, weights=weights, k=1)[0]


def get_microstop(code: str) -> Optional[Microstop]:
    return _MS_BY_CODE.get(code)


def sample_duration(ms: Microstop) -> float:
    """Return a random duration in sim-seconds within the microstop's range."""
    return random.uniform(ms.duration_lo_s, ms.duration_hi_s)
