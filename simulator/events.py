"""
Transaction Event Emitter
─────────────────────────
Writes governed transaction events per DATA_CONTRACT.md.

Phase 1: append to JSONL log file (Node-RED watches this).
Phase 4: MQTT publish will be added here.

All events follow the schema from DATA_CONTRACT.md §3.
"""
import json
import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("events")


class EventEmitter:
    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._enterprise = cfg["enterprise"]["name"]
        self._site       = cfg["enterprise"]["site"]
        self._area       = cfg["enterprise"]["area"]
        self._line       = cfg["enterprise"]["line"]
        self._actor_id   = cfg["simulator"]["instance_id"]
        self._txn_file   = cfg["logging"]["transactions_file"]
        self._console    = cfg["logging"]["console"]
        self._seen_ids: set[str] = set()   # idempotency guard

        os.makedirs(os.path.dirname(self._txn_file) or ".", exist_ok=True)

    # ── Base builder ─────────────────────────────────────────────────────────
    def _base(self, event_type: str, order_id: Optional[str], sku: Optional[str]) -> dict:
        return {
            "eventType":  event_type,
            "eventId":    str(uuid.uuid4()),
            "ts":         datetime.now(timezone.utc).isoformat(),
            "enterprise": self._enterprise,
            "site":       self._site,
            "area":       self._area,
            "line":       self._line,
            "orderId":    order_id,
            "sku":        sku,
            "actor":      {"type": "sim", "id": self._actor_id},
            "validation": {"status": "ACCEPTED", "version": "v1"},
        }

    def _emit(self, evt: dict):
        eid = evt["eventId"]
        if eid in self._seen_ids:
            log.warning("Duplicate event suppressed: %s", eid)
            return
        self._seen_ids.add(eid)
        # Keep idempotency set bounded
        if len(self._seen_ids) > 10_000:
            self._seen_ids = set(list(self._seen_ids)[-5_000:])

        line = json.dumps(evt)
        with open(self._txn_file, "a") as f:
            f.write(line + "\n")
        if self._console:
            log.info("[EVENT] %s  order=%s  sku=%s",
                     evt["eventType"], evt.get("orderId"), evt.get("sku"))

    # ── Specific events ───────────────────────────────────────────────────────
    def state_changed(self, order_id, sku, from_state, to_state,
                      stop_code=None, fault_code=None,
                      reason_id=None, duration_ms=None, fingerprint=None):
        evt = self._base("StateChanged", order_id, sku)
        evt.update({
            "fromState":   from_state,
            "toState":     to_state,
            "stopCode":    stop_code,
            "faultCode":   fault_code,
            "reasonId":    reason_id,
            "durationMs":  duration_ms,
            "fingerprint": fingerprint,
        })
        self._emit(evt)

    def order_started(self, order_id, sku, planned_qty,
                      planned_start_ts, planned_end_ts=None):
        evt = self._base("OrderStarted", order_id, sku)
        evt.update({
            "plannedQty":      planned_qty,
            "plannedStartTs":  planned_start_ts,
            "plannedEndTs":    planned_end_ts,
        })
        self._emit(evt)

    def order_completed(self, order_id, sku,
                        good_delta, reject_delta, duration_ms, yield_pct):
        evt = self._base("OrderCompleted", order_id, sku)
        evt.update({
            "goodCountDelta":   good_delta,
            "rejectCountDelta": reject_delta,
            "durationMs":       duration_ms,
            "yield":            round(yield_pct, 4),
        })
        self._emit(evt)

    def bottle_completed(self, order_id, sku, result, station,
                         reject_reason=None, weight=None, torque=None):
        evt = self._base("BottleCompleted", order_id, sku)
        evt.update({
            "result":       result,     # GOOD | REJECT
            "station":      station,
            "rejectReason": reject_reason,
            "weight":       weight,
            "torque":       torque,
        })
        self._emit(evt)

    def microstop_started(self, order_id, sku, stop_code, fingerprint):
        evt = self._base("MicrostopStarted", order_id, sku)
        evt.update({"stopCode": stop_code, "fingerprint": fingerprint})
        self._emit(evt)

    def microstop_ended(self, order_id, sku, stop_code, duration_ms, fingerprint):
        evt = self._base("MicrostopEnded", order_id, sku)
        evt.update({
            "stopCode":   stop_code,
            "durationMs": duration_ms,
            "fingerprint": fingerprint,
        })
        self._emit(evt)

    def stop_started(self, order_id, sku, stop_code,
                     reason_id=None, reason_text=None):
        evt = self._base("StopStarted", order_id, sku)
        evt.update({
            "stopCode":   stop_code,
            "reasonId":   reason_id,
            "reasonText": reason_text,
        })
        self._emit(evt)

    def stop_ended(self, order_id, sku, stop_code, duration_ms,
                   reason_id=None):
        evt = self._base("StopEnded", order_id, sku)
        evt.update({
            "stopCode":   stop_code,
            "durationMs": duration_ms,
            "reasonId":   reason_id,
        })
        self._emit(evt)

    def fault_raised(self, order_id, sku, fault_code, severity, station):
        evt = self._base("FaultRaised", order_id, sku)
        evt.update({
            "faultCode": fault_code,
            "severity":  severity,
            "station":   station,
        })
        self._emit(evt)

    def fault_cleared(self, order_id, sku, fault_code, station, duration_ms):
        evt = self._base("FaultCleared", order_id, sku)
        evt.update({
            "faultCode":  fault_code,
            "station":    station,
            "durationMs": duration_ms,
        })
        self._emit(evt)

    def cip_started(self, order_id, sku):
        self._emit(self._base("CIPStarted", order_id, sku))

    def cip_ended(self, order_id, sku, duration_ms):
        evt = self._base("CIPEnded", order_id, sku)
        evt["durationMs"] = duration_ms
        self._emit(evt)

    def changeover_started(self, order_id, sku, changeover_type, stop_code):
        evt = self._base("ChangeoverStarted", order_id, sku)
        evt.update({"changeoverType": changeover_type, "stopCode": stop_code})
        self._emit(evt)

    def changeover_completed(self, order_id, sku, changeover_type,
                              stop_code, duration_ms):
        evt = self._base("ChangeoverCompleted", order_id, sku)
        evt.update({
            "changeoverType": changeover_type,
            "stopCode":       stop_code,
            "durationMs":     duration_ms,
        })
        self._emit(evt)
