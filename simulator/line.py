"""
Bottling Line Simulation Engine
────────────────────────────────
Drives the ISA-95 state machine, bottle counting, microstops,
breakdowns, changeovers, and CIP. Updates Modbus registers each tick.

State machine:
  IDLE → CHANGEOVER → RUNNING → MICROSTOP → RUNNING → ...
       → STOPPED   → RUNNING
       → FAULT     → (wait)  → RUNNING
       → CIP       → IDLE / next order

Time model:
  wall_tick_s = 1.0 / tick_hz
  sim_tick_s  = wall_tick_s * speed_factor
  All durations stored in sim-seconds.
"""
import logging
import math
import random
import time
from datetime import datetime, timezone
from typing import Optional

from .config import load_config
from .register_map import (
    TOTAL_REGISTERS, LINE_STATE, STOP_CODE_MAP, REJECT_REASON_MAP,
    R_LINE_STATE, R_LINE_SPEED, R_GOOD_COUNT, R_REJECT_COUNT,
    R_ORDER_IDX, R_SKU_IDX, R_STOP_CODE, R_FAULT_CODE, R_ORDER_SEQ,
    R_SIM_SPEED_X10,
    R_BOTTLE_PRESENCE, R_INFEED_RATE, R_STARVED, R_JAM_DETECTED,
    R_TARGET_WEIGHT, R_ACTUAL_WEIGHT, R_FILL_TIME_MS,
    R_SCALE_STABLE, R_DRIP_SENSOR,
    R_TORQUE_TARGET, R_TORQUE_ACTUAL, R_TORQUE_IN_SPEC, R_CAP_FEED_OK,
    R_GROSS_WEIGHT, R_WEIGHT_IN_SPEC, R_REZERO_ACTIVE,
    R_LABEL_APPLIED, R_LABEL_SENSOR_OK, R_LABEL_STOCK,
    R_BARCODE_OK, R_RESCAN_COUNT,
    R_HAZARD_REQUIRED, R_HAZARD_APPLIED, R_HAZARD_STOCK,
    R_REJECT_TRIGGERED, R_REJECT_REASON, R_PUSHER_CYCLE_MS,
    pack_float32, pack_uint32, bool_reg,
)
from .sku_data import SKUS, SKU_LIST, sku_index, get_sku
from .schedule import ScheduleEntry, load_schedule
from .events import EventEmitter
from .microstops import pick_microstop, sample_duration as ms_duration, MICROSTOPS
from .breakdowns import (
    get_major, sample_duration as bd_duration,
    breakdown_trigger_offset, MINOR_BREAKDOWNS,
)

log = logging.getLogger("line")


class LineSimulator:
    """Complete line simulation — call run() from main thread."""

    def __init__(self, cfg: dict, modbus_server):
        self._cfg    = cfg
        self._mb     = modbus_server
        self._events = EventEmitter(cfg)

        sf = float(cfg["simulator"]["speed_factor"])
        hz = float(cfg["simulator"]["tick_hz"])
        self._speed_factor = sf
        self._wall_tick_s  = 1.0 / hz
        self._sim_tick_s   = self._wall_tick_s * sf

        prod = cfg["production"]
        self._ms_mean_interval  = float(prod["microstop_mean_interval_s"])
        self._base_reject_prob  = float(prod["base_reject_probability"])
        self._label_stock_init  = float(prod["label_stock_initial_pct"])
        self._label_stock_dep   = float(prod["label_stock_depletion_per_1000"])
        self._cap_stock_init    = float(prod["cap_stock_initial_pct"])

        # Master monotonic counters
        self._good_count   = 0
        self._reject_count = 0

        # Current run state
        self._line_state   = "IDLE"
        self._current_order: Optional[ScheduleEntry] = None
        self._current_sku_id: Optional[str] = None
        self._order_seq    = 0

        # Consumable levels
        self._label_stock     = self._label_stock_init
        self._hazard_stock    = self._label_stock_init
        self._cap_stock       = self._cap_stock_init

        # Bottle accumulator (fractional)
        self._bottle_acc = 0.0

        # Timers (in sim-seconds remaining)
        self._stop_remaining    = 0.0
        self._microstop_remaining = 0.0
        self._ms_timer          = 0.0   # time until next microstop check
        self._active_stop_code: Optional[str] = None
        self._active_ms: Optional[object] = None
        self._active_bd: Optional[object] = None

        # Breakdown injection state
        self._bd_inject_at   = None   # sim-seconds into order
        self._bd_elapsed     = 0.0
        self._bd_code        = None

        # Order elapsed
        self._order_elapsed  = 0.0
        self._order_start_good  = 0
        self._order_start_reject = 0
        self._order_start_wall  = 0.0

        # Registers
        self._regs = [0] * TOTAL_REGISTERS
        self._init_registers()

        # Schedule
        schedule_xlsx = cfg["simulator"].get("schedule_xlsx", "")
        self._schedule = load_schedule(schedule_xlsx)

        log.info("LineSimulator ready. speed_factor=%.1fx  tick=%.3fs wall / %.3fs sim",
                 sf, self._wall_tick_s, self._sim_tick_s)

    # ── Register helpers ──────────────────────────────────────────────────────
    def _init_registers(self):
        self._regs[R_LINE_STATE]    = LINE_STATE["IDLE"]
        self._regs[R_ORDER_IDX]     = 0xFFFF
        self._regs[R_SKU_IDX]       = 0xFFFF
        self._regs[R_LABEL_STOCK]   = int(self._label_stock)
        self._regs[R_HAZARD_STOCK]  = int(self._hazard_stock)
        self._regs[R_CAP_FEED_OK]   = 1
        self._regs[R_LABEL_SENSOR_OK] = 1
        self._regs[R_BARCODE_OK]    = 1
        self._regs[R_SCALE_STABLE]  = 1
        h, l = pack_float32(self._speed_factor)
        self._regs[R_SIM_SPEED_X10] = int(self._speed_factor * 10)
        self._push_registers()

    def _push_registers(self):
        """Write the local register array to the Modbus server."""
        self._mb.set_registers(0, self._regs)

    def _set_line_state(self, state: str, stop_code=None, fault_code=None):
        if self._line_state != state:
            from_state = self._line_state
            self._line_state = state
            self._regs[R_LINE_STATE] = LINE_STATE.get(state, 0)
            self._regs[R_STOP_CODE]  = STOP_CODE_MAP.get(stop_code, 0)
            self._regs[R_FAULT_CODE] = self._fault_code_int(fault_code)
            sku = self._current_sku_id
            oid = self._current_order.entry_id if self._current_order else None
            self._events.state_changed(oid, sku, from_state, state,
                                       stop_code=stop_code, fault_code=fault_code)

    def _fault_code_int(self, code) -> int:
        return {"BD-M1": 1, "BD-M2": 2, "BD-M3": 3}.get(code, 0)

    def _write_float(self, reg_hi, value):
        h, l = pack_float32(value)
        self._regs[reg_hi]   = h
        self._regs[reg_hi+1] = l

    def _write_uint32(self, reg_hi, value):
        h, l = pack_uint32(value)
        self._regs[reg_hi]   = h
        self._regs[reg_hi+1] = l

    # ── Noise helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _noise(value, sigma_pct=0.02):
        return value * (1 + random.gauss(0, sigma_pct))

    # ── Main run loop ─────────────────────────────────────────────────────────
    def run(self):
        log.info("Simulation starting. %d schedule entries.", len(self._schedule))
        for entry in self._schedule:
            self._execute_entry(entry)
        log.info("Schedule complete. Total good=%d  reject=%d",
                 self._good_count, self._reject_count)
        self._set_line_state("IDLE")
        self._regs[R_ORDER_IDX] = 0xFFFF
        self._regs[R_SKU_IDX]   = 0xFFFF
        self._push_registers()

    def _execute_entry(self, entry: ScheduleEntry):
        if entry.entry_type == "BREAK":
            self._run_break(entry)
        elif entry.entry_type == "CIP":
            self._run_cip(entry)
        elif entry.entry_type == "ORDER":
            # Preceding changeover?
            if entry.preceding_changeover and entry.changeover_code:
                self._run_changeover(entry)
            self._run_order(entry)
            if entry.cip_after:
                fake_cip = ScheduleEntry(
                    entry_id=f"CIP-auto-{entry.entry_id}",
                    entry_type="CIP", day=entry.day, shift=entry.shift,
                )
                self._run_cip(fake_cip)

    # ── Changeover ────────────────────────────────────────────────────────────
    def _run_changeover(self, entry: ScheduleEntry):
        oid = self._current_order.entry_id if self._current_order else None
        sku = self._current_sku_id
        code = entry.changeover_code
        ctype = entry.changeover_type

        log.info("CHANGEOVER %s (%s) → %s", code, ctype, entry.sku_id)
        self._events.changeover_started(oid, sku, ctype, code)
        self._set_line_state("CHANGEOVER", stop_code=code)
        self._regs[R_STOP_CODE] = STOP_CODE_MAP.get(code, 0)

        dur_s = random.uniform(
            entry.changeover_duration_min_lo * 60,
            entry.changeover_duration_min_hi * 60,
        )
        self._sleep_sim(dur_s, poll_regs=True)

        # Liquid changeover always triggers CIP
        if ctype == "LIQUID":
            self._events.changeover_completed(oid, sku, ctype, code, int(dur_s * 1000))
            fake_cip = ScheduleEntry(
                entry_id=f"CIP-liq-{entry.entry_id}",
                entry_type="CIP", day=entry.day, shift=entry.shift,
            )
            self._run_cip(fake_cip)
        else:
            self._events.changeover_completed(oid, sku, ctype, code, int(dur_s * 1000))

        self._regs[R_STOP_CODE] = 0

    # ── CIP ───────────────────────────────────────────────────────────────────
    def _run_cip(self, entry: ScheduleEntry):
        oid = self._current_order.entry_id if self._current_order else None
        sku = self._current_sku_id

        log.info("CIP starting (45 min sim)")
        self._events.cip_started(oid, sku)
        self._set_line_state("CIP")

        dur_s = entry.cip_duration_min * 60
        self._sleep_sim(dur_s, poll_regs=True)

        self._events.cip_ended(oid, sku, int(dur_s * 1000))
        log.info("CIP complete")

    # ── Break ─────────────────────────────────────────────────────────────────
    def _run_break(self, entry: ScheduleEntry):
        oid = self._current_order.entry_id if self._current_order else None
        sku = self._current_sku_id
        code = "ST04"

        log.info("BREAK — %d min", entry.break_duration_min)
        self._events.stop_started(oid, sku, code, reason_id=4, reason_text="Lunch Break")
        self._set_line_state("STOPPED", stop_code=code)

        dur_s = entry.break_duration_min * 60
        self._sleep_sim(dur_s, poll_regs=True)

        self._events.stop_ended(oid, sku, code, int(dur_s * 1000), reason_id=4)
        self._regs[R_STOP_CODE] = 0

    # ── Order execution ───────────────────────────────────────────────────────
    def _run_order(self, entry: ScheduleEntry):
        self._current_order  = entry
        self._current_sku_id = entry.sku_id
        self._order_seq     += 1

        sku = get_sku(entry.sku_id)
        if not sku:
            log.error("Unknown SKU %s — skipping order %s", entry.sku_id, entry.entry_id)
            return

        self._order_start_good   = self._good_count
        self._order_start_reject = self._reject_count
        self._order_elapsed      = 0.0
        self._bottle_acc         = 0.0
        self._order_start_wall   = time.monotonic()

        # Reset next-microstop timer
        self._ms_timer = self._next_ms_interval()

        # Breakdown injection offset
        bd_code = entry.inject_breakdown
        if bd_code:
            self._bd_code     = bd_code
            self._bd_inject_at = breakdown_trigger_offset(
                entry.planned_qty, sku.nominal_speed_bpm
            )
            self._bd_elapsed  = 0.0
        else:
            self._bd_code      = None
            self._bd_inject_at = None

        # Update registers
        self._regs[R_SKU_IDX]   = sku_index(entry.sku_id)
        self._regs[R_ORDER_IDX] = self._order_seq - 1
        self._regs[R_ORDER_SEQ] = self._order_seq
        self._write_float(R_TARGET_WEIGHT, sku.target_weight_g)
        self._write_float(R_TORQUE_TARGET, sku.torque_target_ncm)
        self._regs[R_HAZARD_REQUIRED] = bool_reg(sku.hazard_flag)

        now_iso = datetime.now(timezone.utc).isoformat()
        self._events.order_started(
            entry.entry_id, entry.sku_id, entry.planned_qty,
            now_iso,
        )
        self._set_line_state("RUNNING")

        log.info("ORDER %s | %s | qty=%d | speed=%d bpm",
                 entry.entry_id, entry.sku_id,
                 entry.planned_qty, sku.nominal_speed_bpm)

        bottles_produced = 0
        while bottles_produced < entry.planned_qty:
            # ── BREAKDOWN injection ──────────────────────────────────────────
            if (self._bd_inject_at is not None
                    and self._bd_elapsed >= self._bd_inject_at):
                bd_obj = get_major(self._bd_code)
                if bd_obj:
                    bottles_produced += self._run_breakdown(bd_obj, entry)
                self._bd_inject_at = None   # only inject once

            # ── MICROSTOP check ──────────────────────────────────────────────
            if self._line_state == "RUNNING":
                self._ms_timer -= self._sim_tick_s
                if self._ms_timer <= 0:
                    ms = pick_microstop(entry.sku_id)
                    bottles_produced += self._run_microstop(ms, entry, sku)
                    self._ms_timer = self._next_ms_interval()

            # ── Normal bottle production ─────────────────────────────────────
            if self._line_state == "RUNNING":
                self._bottle_acc += (sku.nominal_speed_bpm / 60.0) * self._sim_tick_s

                while self._bottle_acc >= 1.0 and bottles_produced < entry.planned_qty:
                    self._bottle_acc -= 1.0
                    good = self._process_bottle(sku, entry)
                    if good:
                        bottles_produced += 1
                    # Deplete stocks
                    self._label_stock = max(0, self._label_stock
                                           - self._label_stock_dep / 1000)
                    if sku.hazard_flag:
                        self._hazard_stock = max(0, self._hazard_stock
                                                - self._label_stock_dep / 1000)

                # Update line-level signals
                self._update_line_signals(sku)

                # BD elapsed tracking
                if self._bd_inject_at is not None:
                    self._bd_elapsed += self._sim_tick_s

            self._push_registers()
            time.sleep(self._wall_tick_s)
            self._order_elapsed += self._sim_tick_s

        # ── Order complete ───────────────────────────────────────────────────
        good_delta   = self._good_count   - self._order_start_good
        reject_delta = self._reject_count - self._order_start_reject
        planned_qty  = entry.planned_qty
        yield_pct    = good_delta / max(planned_qty, 1)
        dur_ms       = int((time.monotonic() - self._order_start_wall) * 1000)

        self._events.order_completed(
            entry.entry_id, entry.sku_id,
            good_delta, reject_delta,
            dur_ms, yield_pct,
        )
        log.info("ORDER %s COMPLETE | good=%d  reject=%d  yield=%.1f%%",
                 entry.entry_id, good_delta, reject_delta, yield_pct * 100)

    # ── Bottle processing ─────────────────────────────────────────────────────
    def _process_bottle(self, sku, entry: ScheduleEntry) -> bool:
        """Simulate one bottle through all stations. Returns True if good."""
        reject_reason = None

        # Filler01 — noise σ=0.5%, tolerance=±2% → ~P(reject)≈0.3% from weight
        actual_w = self._noise(sku.target_weight_g, 0.005)
        fill_t_ms = int(self._noise(sku.fill_time_ms, 0.02))
        weight_ok = abs(actual_w - sku.target_weight_g) <= sku.target_weight_g * 0.02
        self._write_float(R_ACTUAL_WEIGHT, actual_w)
        self._write_uint32(R_FILL_TIME_MS, fill_t_ms)
        self._regs[R_SCALE_STABLE] = 1
        self._regs[R_DRIP_SENSOR]  = bool_reg(random.random() < 0.02)
        self._write_float(R_GROSS_WEIGHT, actual_w)
        self._regs[R_WEIGHT_IN_SPEC] = bool_reg(weight_ok)
        if not weight_ok:
            reject_reason = "weight"

        # Capper01 — noise σ=1%, tolerance=±5% → ~P(reject)≈0.05% from torque
        actual_t = self._noise(sku.torque_target_ncm, 0.01)
        torque_ok = abs(actual_t - sku.torque_target_ncm) <= sku.torque_target_ncm * 0.05
        self._write_float(R_TORQUE_ACTUAL, actual_t)
        self._regs[R_TORQUE_IN_SPEC] = bool_reg(torque_ok)
        self._regs[R_CAP_FEED_OK]    = 1
        if not torque_ok and reject_reason is None:
            reject_reason = "torque"

        # Scanner01 — 0.5% first-scan failure; rescan resolves most; rare reject
        barcode_ok = random.random() > 0.005
        self._regs[R_BARCODE_OK]   = bool_reg(barcode_ok)
        self._regs[R_RESCAN_COUNT] = 0 if barcode_ok else random.randint(1, 2)
        if not barcode_ok and random.random() < 0.1 and reject_reason is None:
            # Only 10% of barcode failures become rejects (rest resolve on rescan)
            reject_reason = "barcode"

        # Labeller01
        self._regs[R_LABEL_APPLIED]   = 1
        self._regs[R_LABEL_SENSOR_OK] = 1
        self._regs[R_LABEL_STOCK]     = min(100, max(0, int(self._label_stock)))

        # Labeller02 (hazard)
        hazard_ok = True
        if sku.hazard_flag:
            hazard_ok = self._hazard_stock > 2
            self._regs[R_HAZARD_REQUIRED] = 1
            self._regs[R_HAZARD_APPLIED]  = bool_reg(hazard_ok)
            self._regs[R_HAZARD_STOCK]    = min(100, max(0, int(self._hazard_stock)))
            if not hazard_ok and reject_reason is None:
                reject_reason = "hazard_label"
        else:
            self._regs[R_HAZARD_REQUIRED] = 0
            self._regs[R_HAZARD_APPLIED]  = 0

        # Final reject decision
        extra_reject = random.random() < self._base_reject_prob
        if extra_reject and reject_reason is None:
            reject_reason = "weight"   # generic quality reject

        is_good = reject_reason is None

        # RejectPusher01
        cycle_ms = random.randint(200, 500) if is_good else random.randint(500, 800)
        self._write_uint32(R_PUSHER_CYCLE_MS, cycle_ms)
        self._regs[R_REJECT_TRIGGERED]  = bool_reg(not is_good)
        self._regs[R_REJECT_REASON]     = REJECT_REASON_MAP.get(reject_reason, 0)

        # Update counters
        if is_good:
            self._good_count += 1
        else:
            self._reject_count += 1

        self._write_uint32(R_GOOD_COUNT,   self._good_count)
        self._write_uint32(R_REJECT_COUNT, self._reject_count)

        # Emit BottleCompleted (sampled — emit 1 in 50 to avoid flooding log)
        if random.random() < 0.02:
            self._events.bottle_completed(
                entry.entry_id, entry.sku_id,
                "GOOD" if is_good else "REJECT",
                "RejectPusher01" if not is_good else "Checkweigher01",
                reject_reason=reject_reason,
                weight=round(actual_w, 2),
                torque=round(actual_t, 2),
            )

        return is_good

    # ── Microstop ─────────────────────────────────────────────────────────────
    def _run_microstop(self, ms, entry: ScheduleEntry, sku) -> int:
        """Simulate a microstop. Returns 0 (no extra good bottles during stop)."""
        fp = ms.fingerprint_fn()
        dur_sim_s = ms_duration(ms)

        self._events.microstop_started(
            entry.entry_id, entry.sku_id, ms.code, fp
        )
        self._set_line_state("MICROSTOP", stop_code=ms.code)
        self._regs[R_STOP_CODE] = STOP_CODE_MAP.get(ms.code, 0)

        # Apply signal mutations
        ms.mutations_fn(self._regs)

        self._sleep_sim(dur_sim_s, poll_regs=True)

        # Restore affected signals
        self._regs[R_SCALE_STABLE]    = 1
        self._regs[R_DRIP_SENSOR]     = 0
        self._regs[R_CAP_FEED_OK]     = 1
        self._regs[R_REZERO_ACTIVE]   = 0
        self._regs[R_LABEL_SENSOR_OK] = 1
        self._regs[R_BARCODE_OK]      = 1
        self._regs[R_BOTTLE_PRESENCE] = 1

        self._events.microstop_ended(
            entry.entry_id, entry.sku_id, ms.code,
            int(dur_sim_s * 1000), fp,
        )
        self._set_line_state("RUNNING")
        self._regs[R_STOP_CODE] = 0
        return 0

    # ── Major breakdown ───────────────────────────────────────────────────────
    def _run_breakdown(self, bd, entry: ScheduleEntry) -> int:
        oid = entry.entry_id
        sku_id = entry.sku_id
        dur_sim_s = bd_duration(bd)

        log.warning("BREAKDOWN %s — %s (%s) — %.0f min sim",
                    bd.code, bd.name, bd.station, dur_sim_s / 60)

        self._events.fault_raised(oid, sku_id, bd.code, bd.severity, bd.station)
        self._events.stop_started(oid, sku_id, bd.code)
        self._set_line_state("FAULT", fault_code=bd.code, stop_code=bd.code)
        self._regs[R_FAULT_CODE] = self._fault_code_int(bd.code)
        self._regs[R_STOP_CODE]  = STOP_CODE_MAP.get(bd.code, 0)

        # Signal mutations during fault
        if bd.code == "BD-M1":
            self._regs[R_SCALE_STABLE] = 0
        elif bd.code == "BD-M2":
            self._regs[R_TORQUE_IN_SPEC] = 0
        elif bd.code == "BD-M3":
            self._regs[R_REZERO_ACTIVE] = 1

        self._sleep_sim(dur_sim_s, poll_regs=True)

        # Clear
        self._regs[R_SCALE_STABLE]   = 1
        self._regs[R_TORQUE_IN_SPEC] = 1
        self._regs[R_REZERO_ACTIVE]  = 0
        self._regs[R_FAULT_CODE]     = 0
        self._regs[R_STOP_CODE]      = 0

        self._events.fault_cleared(oid, sku_id, bd.code, bd.station, int(dur_sim_s * 1000))
        self._events.stop_ended(oid, sku_id, bd.code, int(dur_sim_s * 1000))
        self._set_line_state("RUNNING")
        return 0

    # ── Signal updates (called every tick during RUNNING) ─────────────────────
    def _update_line_signals(self, sku):
        speed = self._noise(sku.nominal_speed_bpm, 0.01)
        self._write_float(R_LINE_SPEED, speed)
        self._write_float(R_INFEED_RATE, self._noise(speed, 0.015))

        self._regs[R_BOTTLE_PRESENCE] = 1
        self._regs[R_STARVED]         = 0
        self._regs[R_JAM_DETECTED]    = 0

        # Torque target stable update
        self._write_float(R_TORQUE_TARGET, sku.torque_target_ncm)
        self._write_float(R_TARGET_WEIGHT, sku.target_weight_g)

    # ── Sleep (sim time, with register pushes) ────────────────────────────────
    def _sleep_sim(self, sim_s: float, poll_regs: bool = False):
        """Sleep for sim_s sim-seconds worth of wall clock time."""
        wall_s = sim_s / self._speed_factor
        start  = time.monotonic()
        while (time.monotonic() - start) < wall_s:
            if poll_regs:
                self._push_registers()
            time.sleep(self._wall_tick_s)
        if poll_regs:
            self._push_registers()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _next_ms_interval(self) -> float:
        """Exponential inter-arrival for microstops (Poisson process)."""
        return random.expovariate(1.0 / self._ms_mean_interval)
