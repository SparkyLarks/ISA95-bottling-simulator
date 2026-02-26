"""
Production Schedule — built-in data + optional Excel loader.

The built-in schedule mirrors Production_Schedule sheet exactly.
If the Excel file is found at startup, it overrides the built-in data.

Each schedule entry is either:
  - A production ORDER (has sku_id, planned_qty, work_master_id)
  - A CHANGEOVER event (has changeover_type, duration_s range)
  - A CIP event
  - A BREAK event
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("schedule")

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ScheduleEntry:
    entry_id: str            # ORD-001, CIP-001, etc.
    entry_type: str          # ORDER | CHANGEOVER | CIP | BREAK
    day: str
    shift: str

    # ORDER fields
    work_master_id: str = ""
    sku_id: Optional[str] = None
    planned_qty: int = 0

    # CHANGEOVER fields
    changeover_type: str = ""   # LABEL | SIZE | LIQUID
    changeover_code: str = ""   # ST01 / ST02 / ST03
    changeover_duration_min_lo: int = 0
    changeover_duration_min_hi: int = 0

    # CIP
    cip_duration_min: int = 45

    # BREAK
    break_duration_min: int = 30

    # Breakdown to inject during this order (optional)
    inject_breakdown: Optional[str] = None   # BD-M1 / BD-M2 / BD-M3

    # CIP follows this order?
    cip_after: bool = False

    # Preceding changeover (set by loader from "Preceding Event" column)
    preceding_changeover: Optional[str] = None  # ST01/ST02/ST03

    notes: str = ""


# ── Built-in schedule (mirrors Production_Schedule sheet) ────────────────────

BUILT_IN_SCHEDULE: list[ScheduleEntry] = [
    # Monday Shift 1
    ScheduleEntry("ORD-001","ORDER","Mon","Shift 1","WM-002","LEM-500-IE",4000,
                  cip_after=False, notes="Opening order"),
    ScheduleEntry("ORD-002","ORDER","Mon","Shift 1","WM-001","LEM-200-IE",3000,
                  preceding_changeover="ST01",
                  changeover_code="ST01", changeover_type="LABEL",
                  changeover_duration_min_lo=20, changeover_duration_min_hi=25,
                  notes="Label changeover LBL-A"),
    ScheduleEntry("ORD-003","ORDER","Mon","Shift 1","WM-003","LEM-2L-IE",1200,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=40, changeover_duration_min_hi=50,
                  inject_breakdown="BD-M1",
                  notes="Size change 200→2L. BD-M1 injected"),
    ScheduleEntry("CIP-001","CIP","Mon","Shift 1", cip_duration_min=45,
                  notes="After 3rd order"),

    # Monday Shift 2
    ScheduleEntry("ORD-004","ORDER","Mon","Shift 2","WM-005","COL-500-IE",3800,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="Liquid change Still→Cola. CO includes CIP."),
    ScheduleEntry("ORD-005","ORDER","Mon","Shift 2","WM-006","DC-500-IE",2500,
                  inject_breakdown="BD-M2",
                  notes="Hazard SKU. BD-M2 injected"),
    ScheduleEntry("ORD-006-BRK","BREAK","Mon","Shift 2", break_duration_min=30,
                  notes="Lunch break"),
    ScheduleEntry("ORD-006","ORDER","Mon","Shift 2","WM-005","COL-2L-IE",800,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=35, changeover_duration_min_hi=45,
                  notes="Size change 500→2L"),

    # Tuesday Shift 1
    ScheduleEntry("ORD-007","ORDER","Tue","Shift 1","WM-002","LEM-500-IE",5000,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  inject_breakdown="BD-M3",
                  notes="Liquid change Cola→Lemon. BD-M3 injected"),
    ScheduleEntry("ORD-008","ORDER","Tue","Shift 1","WM-002","LEM-500-IE",4000,
                  notes="Continuation same SKU"),
    ScheduleEntry("ORD-009","ORDER","Tue","Shift 1","WM-004","LEM-6L-IE",300,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=40, changeover_duration_min_hi=55,
                  cip_after=True,
                  notes="6L format. High MS02 risk. CIP after."),
    ScheduleEntry("CIP-002","CIP","Tue","Shift 1", cip_duration_min=45,
                  notes="After 4th order"),

    # Tuesday Shift 2
    ScheduleEntry("ORD-010","ORDER","Tue","Shift 2","WM-006","DC-500-UK",2000,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="UK hazard variant. Liquid CO."),
    ScheduleEntry("ORD-011","ORDER","Tue","Shift 2","WM-002","LEM-500-IE",4500,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="Long order. Cola→Still. Minor stops here."),

    # Wednesday Shift 1
    ScheduleEntry("ORD-012","ORDER","Wed","Shift 1","WM-001","LEM-200-IE",5000,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=35, changeover_duration_min_hi=50,
                  notes="500→200mL"),
    ScheduleEntry("ORD-013","ORDER","Wed","Shift 1","WM-003","LEM-2L-IE",1500,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=40, changeover_duration_min_hi=55,
                  notes="200→2L"),
    ScheduleEntry("ORD-014","ORDER","Wed","Shift 1","WM-002","LEM-500-IE",3500,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=35, changeover_duration_min_hi=45,
                  cip_after=True, notes="4th order — CIP follows"),
    ScheduleEntry("CIP-003","CIP","Wed","Shift 1", cip_duration_min=45),

    # Wednesday Shift 2
    ScheduleEntry("ORD-015","ORDER","Wed","Shift 2","WM-005","COL-500-IE",4000,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="Still→Cola"),
    ScheduleEntry("ORD-015-BRK","BREAK","Wed","Shift 2", break_duration_min=30),
    ScheduleEntry("ORD-016","ORDER","Wed","Shift 2","WM-002","LEM-500-IE",3000,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="Cola→Still"),

    # Thursday Shift 1
    ScheduleEntry("ORD-017","ORDER","Thu","Shift 1","WM-002","LEM-500-IE",5000,
                  notes="Long run — minor stops distributed"),

    # Thursday Shift 2
    ScheduleEntry("ORD-018","ORDER","Thu","Shift 2","WM-006","DC-500-IE",3500,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="Hazard run"),

    # Friday Shift 1
    ScheduleEntry("ORD-019","ORDER","Fri","Shift 1","WM-002","LEM-500-IE",4500,
                  preceding_changeover="ST03",
                  changeover_code="ST03", changeover_type="LIQUID",
                  changeover_duration_min_lo=60, changeover_duration_min_hi=90,
                  notes="End of week"),

    # Friday Shift 2
    ScheduleEntry("ORD-020","ORDER","Fri","Shift 2","WM-001","LEM-200-IE",4000,
                  preceding_changeover="ST02",
                  changeover_code="ST02", changeover_type="SIZE",
                  changeover_duration_min_lo=35, changeover_duration_min_hi=45,
                  notes="Final order"),
]


def load_schedule(xlsx_path: str = None) -> list[ScheduleEntry]:
    """Return built-in schedule. Excel loading reserved for future extension."""
    if xlsx_path and os.path.exists(xlsx_path):
        log.info("Excel schedule found at %s — using built-in (Excel loader Phase 2)", xlsx_path)
    else:
        log.info("Using built-in production schedule (%d entries)", len(BUILT_IN_SCHEDULE))
    return list(BUILT_IN_SCHEDULE)
