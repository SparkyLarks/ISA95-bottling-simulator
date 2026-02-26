# STATE_MACHINE_SPEC.md
## Bottling Line Demo — State Machine Specification (Phase 1)

**Project:** Bottling Line Digital Twin & MDEA Demo  
**Scope:** Simulator control + event emission + historian interpretation  
**Version:** 1.0  
**Date:** 2026-02-26  

---

# 0) Purpose

Define a single, authoritative state model for the Bottling Line simulator.

This document governs:

- How the simulator behaves
- How telemetry and transaction events are emitted
- How stops, microstops, faults, changeovers, and CIP are classified
- How master counts remain monotonic and correct

The state machine must be deterministic given the same inputs, regardless of implementation language.

---

# 1) Key Principles (Non-negotiables)

1. **Master counts are monotonic.**  
   `good_count_master` and `reject_count_master` never reset.

2. **Telemetry never blocks.**  
   Telemetry continues during all states (with meaningful values), unless the station is physically inactive.

3. **Transactions are governed.**  
   State changes emit transaction events and are validated against allowed transitions.

4. **Operator-coded reasons apply only to longer stops.**  
   Microstops are **derived** from signals/patterns and are not visible to the operator UI.

5. **Single source of truth:**  
   The `line_state` is the authoritative operational mode for the simulator.

---

# 2) Entities & Scope

## 2.1 Entities
- **Line:** `Line01`
- **Stations:** Infeed01, Filler01, Capper01, Checkweigher01, Labeller01, Scanner01, Labeller02 (conditional), RejectPusher01, CIP01

## 2.2 State Machine Applies To
- **Primary:** Line-level state machine (Line01)
- **Secondary:** Station-level “active/inactive” flags derived from line state (e.g., Filler active only when RUNNING or MICROSTOP recovery is complete)

---

# 3) State Definitions (Line-Level)

| State | Meaning | Production Allowed? | Notes |
|------|---------|---------------------|------|
| **IDLE** | No order running, line waiting | No | Default when no order active |
| **RUNNING** | Normal production execution | Yes | Bottles can complete (good/reject) |
| **MICROSTOP** | Short interruption (3–120s) inferred from signals | No | Not operator-coded; derived |
| **STOPPED** | Longer stop (>5 min) but not a fault state | No | Can be operator-coded |
| **FAULT** | Fault latched; maintenance required | No | Fault code present |
| **CHANGEOVER** | Planned changeover (label/size/liquid) | No | Scheduled/planned |
| **CIP** | Cleaning-in-place execution | No | Scheduled/planned |
| **STARVED** | No bottles/caps/materials available | No | May be fault-driven or operator-coded |
| **BLOCKED** | Outfeed full/blocked | No | May be fault-driven or operator-coded |

> Note: `STARVED` and `BLOCKED` are explicit states (not subtypes of STOPPED) because they produce distinct patterns and analytics.

---

# 4) Stop Duration Thresholds (Config)

These are configuration values (not hard-coded):

- `MICROSTOP_MIN_SEC` = 3
- `MICROSTOP_MAX_SEC` = 120
- `LONG_STOP_MIN_SEC` = 300 (5 minutes)

A stop shorter than `MICROSTOP_MIN_SEC` is ignored (noise).

---

# 5) Inputs & Derived Signals

## 5.1 Core Inputs (Simulator internal)
- `current_order_id`
- `current_sku`
- `order_active` (bool)
- `scheduled_blocks` (changeover, lunch, CIP, planned downtime)
- `fault_injection_events` (breakdowns, minor issues)

## 5.2 Telemetry Signals Used for Detection (Emitted + Used)
- `line_speed_bpm`
- `bottle_presence`
- `infeed_rate_bpm`
- `cap_feed_ok`
- `outfeed_full`
- `scale_stable`
- `drip_sensor`
- `torque_in_spec`
- `barcode_read_ok`
- `rezero_active`
- `reject_triggered`
- `pusher_cycle_time_ms`
- `label_stock_level`, `cap_stock_level` (optional)
- `jam_detected` (optional)

## 5.3 Derived Signals
- `production_active` = line_state == RUNNING
- `station_active[Station]` (true only when station can physically process product)
- `microstop_candidate` (detected pattern)
- `stop_reason_candidate` (derived from signals if operator reason not provided)

---

# 6) Event Emission Rules

## 6.1 Transaction Events (Required)
Emitted on state transitions and significant lifecycle events:

- `OrderStarted`
- `OrderCompleted`
- `StateChanged` (line_state transitions)
- `MicrostopStarted` / `MicrostopEnded`
- `StopStarted` / `StopEnded`
- `FaultRaised` / `FaultCleared`
- `ChangeoverStarted` / `ChangeoverCompleted`
- `CIPStarted` / `CIPEnded`
- `BottleCompleted` (good/reject)

## 6.2 Telemetry (Continuous)
Telemetry continues across all states:
- In RUNNING: normal values
- In MICROSTOP/STOPPED/FAULT: speed becomes 0 or near-0; station-specific signals reflect block/starve/fault
- In CHANGEOVER/CIP: speed 0; additional mode flags emitted

---

# 7) Allowed Transitions (Line-Level)

## 7.1 Transition Table

| From | To | Trigger | Conditions | Emit |
|------|----|---------|------------|------|
| IDLE | RUNNING | OrderStarted | order_active=true AND no scheduled block | OrderStarted + StateChanged |
| RUNNING | MICROSTOP | microstop_candidate | duration within microstop window | MicrostopStarted + StateChanged |
| MICROSTOP | RUNNING | microstop_resolved | candidate cleared | MicrostopEnded + StateChanged |
| RUNNING | STOPPED | stop_duration > LONG_STOP_MIN | not fault-latched | StopStarted + StateChanged |
| STOPPED | RUNNING | stop_resolved | order_active=true AND no block | StopEnded + StateChanged |
| RUNNING | FAULT | fault_latched | fault_code present | FaultRaised + StateChanged |
| FAULT | RUNNING | fault_cleared | fault cleared + reset/ack | FaultCleared + StateChanged |
| RUNNING | STARVED | starvation_condition | bottle_presence=0 OR cap_feed_ok=false for > threshold | StopStarted(type=STARVED) + StateChanged |
| STARVED | RUNNING | starvation_resolved | materials restored | StopEnded + StateChanged |
| RUNNING | BLOCKED | outfeed_condition | outfeed_full=true for > threshold | StopStarted(type=BLOCKED) + StateChanged |
| BLOCKED | RUNNING | outfeed_resolved | outfeed_full=false | StopEnded + StateChanged |
| RUNNING | CHANGEOVER | schedule_start | planned changeover block begins | ChangeoverStarted + StateChanged |
| CHANGEOVER | RUNNING | schedule_end | changeover complete | ChangeoverCompleted + StateChanged |
| RUNNING | CIP | schedule_start | CIP block begins | CIPStarted + StateChanged |
| CIP | RUNNING | schedule_end | CIP complete | CIPEnded + StateChanged |
| ANY | IDLE | OrderCompleted | order_active=false | OrderCompleted + StateChanged |

## 7.2 Transition Precedence (Conflict Resolution)

When multiple triggers occur, apply this priority order:

1. **FAULT** (highest priority; overrides everything)
2. **CIP**
3. **CHANGEOVER**
4. **BLOCKED**
5. **STARVED**
6. **STOPPED** (generic long stop)
7. **MICROSTOP**
8. **RUNNING**
9. **IDLE** (fallback when no order)

This precedence ensures deterministic behavior.

---

# 8) Microstop Detection Rules (Derived)

Microstops are inferred from short interruptions that match a known fingerprint.

A microstop must:
- last between `MICROSTOP_MIN_SEC` and `MICROSTOP_MAX_SEC`
- occur while an order is active
- not be explained by FAULT / CHANGEOVER / CIP / long STOPPED

## 8.1 Microstop Assignment Strategy

When line_speed drops below a threshold for microstop duration, classify using fingerprint matching:

### Example Signals → Microstop Codes
- MS02 Fill Stabilisation Wait:
  - scale_stable=false
  - fill_time_ms elevated vs expected (volume / fill_rate)
- MS04 Cap Feed Stutter:
  - cap_feed_ok=false briefly
  - missing torque sample on a cycle
- MS08 Barcode Re-scan:
  - barcode_read_ok=false then true within 30s
  - rescan_count increments

If no fingerprint matches, classify as `MS00_UNKNOWN`.

---

# 9) Bottle Completion & Counts

A `BottleCompleted` event occurs only in `RUNNING`.

On each completion:
- Determine result: GOOD or REJECT
- Increment monotonic counters:
  - `good_count_master += 1` OR `reject_count_master += 1`

**Counts must never increment in:**
- CHANGEOVER
- CIP
- FAULT
- STOPPED / STARVED / BLOCKED
- MICROSTOP

> If the simulator injects a reject scenario, it emits `BottleCompleted(result=REJECT, reason=...)`.

---

# 10) Operator Reason Codes vs Derived Microstops

## 10.1 Operator Reason Codes (Tablet)
Apply only to:
- STOPPED / STARVED / BLOCKED / CHANGEOVER / CIP / FAULT
when duration > LONG_STOP_MIN_SEC

These are stored as:
- `ReasonID` (numeric)
- `ReasonText` (operator selection)

## 10.2 Microstops (Hidden)
Microstops are not shown to operator UI and are not recorded by tablet.
They are revealed later via historian analysis and MCP pattern discovery.

---

# 11) Required Data in StateChanged Transaction

Every `StateChanged` event must include:

- `eventId`
- `ts`
- `line` / hierarchy context
- `fromState`, `toState`
- `orderId` (nullable if IDLE)
- `sku` (nullable if IDLE)
- `reasonCode` (stopCode where applicable)
- `faultCode` (if FAULT)
- `duration` (if ending a stop)
- `fingerprint` (if microstop)

---

# 12) Acceptance Tests (Simulator)

The state machine implementation is accepted when:

1. No invalid transitions occur (as per Section 7)
2. Precedence rules behave deterministically
3. Counts increment only in RUNNING
4. Microstops are emitted only within microstop duration window
5. Long stops emit operator reason codes (ReasonID) when applicable
6. Fault states always override microstop/stop classifications
7. Week schedule produces:
   - planned changeovers
   - CIP block(s)
   - 3 major breakdowns
   - realistic distribution of microstops and longer stops

---

# END