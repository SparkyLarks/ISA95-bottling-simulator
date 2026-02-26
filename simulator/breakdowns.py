"""
Breakdown Definitions — Major (BD-M1/M2/M3) and Minor
"""
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class Breakdown:
    code: str
    name: str
    station: str
    severity: str       # Major | Minor
    duration_lo_s: float
    duration_hi_s: float
    stop_code: str
    fault_description: str


MAJOR_BREAKDOWNS: dict[str, Breakdown] = {
    "BD-M1": Breakdown(
        code="BD-M1", name="Filler Scale Failure",
        station="Filler01", severity="Major",
        duration_lo_s=45 * 60, duration_hi_s=75 * 60,
        stop_code="BD-M1",
        fault_description="Load cell on Filler01 scale unresponsive. "
                          "Scale_stable permanently false. actual_weight_g unreliable.",
    ),
    "BD-M2": Breakdown(
        code="BD-M2", name="Capper Torque Sensor Failure",
        station="Capper01", severity="Major",
        duration_lo_s=45 * 60, duration_hi_s=75 * 60,
        stop_code="BD-M2",
        fault_description="Torque sensor on Capper01 returning null/zero. "
                          "torque_in_spec=false continuously. All caps unverified.",
    ),
    "BD-M3": Breakdown(
        code="BD-M3", name="Checkweigher Loadcell Failure",
        station="Checkweigher01", severity="Major",
        duration_lo_s=45 * 60, duration_hi_s=75 * 60,
        stop_code="BD-M3",
        fault_description="Checkweigher01 load cell drift. "
                          "gross_weight_g stuck or erratic. rezero_active=true continuously.",
    ),
}

MINOR_BREAKDOWNS: list[Breakdown] = [
    Breakdown("BD-MINOR-PE", "Photoeye Misalignment", "Infeed01",
              "Minor", 5*60, 20*60, "BD-MINOR-PE",
              "Photoeye on Infeed01 misaligned. bottle_presence unreliable."),
    Breakdown("BD-MINOR-LS", "Label Sensor Cleaning", "Labeller01",
              "Minor", 5*60, 20*60, "BD-MINOR-LS",
              "Label sensor on Labeller01 contaminated. label_sensor_ok flickering."),
    Breakdown("BD-MINOR-CA", "Cap Chute Adjustment", "Capper01",
              "Minor", 5*60, 20*60, "BD-MINOR-CA",
              "Cap chute on Capper01 jammed. cap_feed_ok=false."),
]


def get_major(code: str) -> Optional[Breakdown]:
    return MAJOR_BREAKDOWNS.get(code)


def sample_duration(bd: Breakdown) -> float:
    return random.uniform(bd.duration_lo_s, bd.duration_hi_s)


def breakdown_trigger_offset(planned_qty: int, speed_bpm: float) -> float:
    """Return sim-seconds into the order at which to inject the breakdown.
    Aim for roughly 20-40% into the order."""
    order_duration_s = (planned_qty / speed_bpm) * 60
    frac = random.uniform(0.20, 0.40)
    return order_duration_s * frac
