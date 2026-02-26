# Scope of Work (SOW)
## Bottling Line Digital Twin & Model-Driven Event Architecture Demo

**Project Name:** Model-Driven Bottling Line Simulator  
**Client:** Internal Demo / Training Platform  
**Owner:** Amárach StackWorks  
**Version:** 1.0  
**Date:** 2026-02-21  

---

# 1. Purpose

To design and implement a realistic bottling line simulator that:

1. Demonstrates ISA-95 aligned architecture
2. Generates realistic production behavior
3. Emits governed telemetry and transaction events
4. Simulates faults, microstops, changeovers, and CIP
5. Supports historian analysis and AI interrogation
6. Provides a foundation for i3X-style contextual API exposure

This simulator is not a game. It must reflect industrial realism.

---

# 2. System Overview

The system will simulate a single production line:

## Line01 – Bottling Line

Stations:

- Infeed01 (Bottle supply)
- Filler01 (Fill-by-weight)
- Capper01 (Torque measurement)
- Checkweigher01
- Labeller01 (Primary label)
- Scanner01 (Barcode)
- Labeller02 (Secondary/hazard label)
- RejectPusher01
- CIP01

---

# 3. Deliverables

## 3.1 Excel Master Data

### A. SKU & BOM Workbook
Contains:
- Liquid base definitions (Lemon, Diet Lemon, Cola, Diet Cola)
- SKU definitions
- Volume
- Market label
- Hazard flag
- Component requirements per unit

### B. Bill of Resources (BOR)
Defines:
- Required equipment per SKU
- Conditional secondary label logic
- Resource requirements for CIP

### C. Weekly Production Schedule
- 2 shifts per day
- 5 days
- Orders ranging 20 min – 6 hours
- 3 planned changeovers
- 1 CIP cycle after 3–4 orders
- 3 major breakdowns inserted
- Minor breakdowns + microstops distributed

---

## 3.2 Python Simulator Engine

### Core Capabilities

The simulator shall:

1. Execute scheduled orders
2. Simulate changeovers
3. Simulate CIP
4. Emit live telemetry per station
5. Emit transaction events
6. Maintain master good/reject counters
7. Simulate realistic downtime behavior

---

# 4. Fill Logic

## Constant Fill Rate Model

FillRate = 120 mL/sec (configurable)

FillTime = Volume / FillRate

Examples:

- 200mL → 1.67 sec
- 500mL → 4.17 sec
- 2L → 16.67 sec
- 6L → 50 sec

Random noise: ±2–5%

---

# 5. Live Telemetry Signals

Each station must emit realistic signals.

## 5.1 Infeed01
- bottle_presence (bool)
- infeed_rate_bpm (float)
- starved (bool)
- jam_detected (bool)

## 5.2 Filler01
- target_weight_g
- actual_weight_g
- fill_time_ms
- scale_stable
- drip_sensor

## 5.3 Capper01
- torque_target_ncm
- torque_actual_ncm
- torque_in_spec
- cap_feed_ok

## 5.4 Checkweigher01
- gross_weight_g
- weight_in_spec
- rezero_active

## 5.5 Labeller01
- label_applied
- label_sensor_ok
- label_stock_level

## 5.6 Scanner01
- barcode_read_ok
- barcode_string
- rescan_count

## 5.7 Labeller02
- hazard_label_required
- hazard_label_applied
- hazard_label_stock

## 5.8 RejectPusher01
- reject_triggered
- reject_reason_code
- pusher_cycle_time_ms

## 5.9 Line-Level
- line_state (IDLE/RUNNING/MICROSTOP/STOPPED/FAULT/CHANGEOVER/CIP)
- line_speed_bpm
- good_count (monotonic)
- reject_count (monotonic)
- current_order_id
- current_sku

---

# 6. Stop & Downtime Model

## 6.1 Microstops (3–120 sec)

10 defined microstops with fingerprints:

| Code | Name | Typical Duration |
|------|------|------------------|
| MS01 | Infeed Misfeed | 6–25s |
| MS02 | Fill Stabilisation Wait | 8–40s |
| MS03 | Nozzle Drip Detect | 5–20s |
| MS04 | Cap Feed Stutter | 10–50s |
| MS05 | Torque Recheck | 12–60s |
| MS06 | Checkweigher Re-zero | 10–90s |
| MS07 | Label Peelback | 8–45s |
| MS08 | Barcode Re-scan | 5–30s |
| MS09 | Reject Pusher Slow Return | 8–35s |
| MS10 | Outfeed Accumulation Nudge | 15–120s |

Each microstop must:
- Emit StopStarted/StopEnded
- Emit station fingerprint
- Not exceed 120 sec

---

## 6.2 Longer Stops (>5 minutes)

10 longer stop types:

| Code | Name | Duration |
|------|------|----------|
| ST01 | Label Changeover | 20–40 min |
| ST02 | Size Changeover | 35–60 min |
| ST03 | Liquid Changeover | 60–120 min |
| ST04 | Lunch Break | 30 min |
| ST05 | Bottle Starved | 5–25 min |
| ST06 | Outfeed Blocked | 5–30 min |
| ST07 | Label Stockout | 10–45 min |
| ST08 | Cap Stockout | 10–60 min |
| ST09 | Conveyor Jam | 8–35 min |
| ST10 | Quality Inspection Hold | 15–90 min |

---

## 6.3 Major Breakdowns (3 per week)

Each ~60 min:

- BD-M1: Filler Scale Failure
- BD-M2: Capper Torque Sensor Failure
- BD-M3: Checkweigher Loadcell Failure

---

## 6.4 Minor Breakdowns

5–20 min:

- Photoeye Misalignment
- Label Sensor Cleaning
- Cap Chute Adjustment

---

# 7. Changeover Logic

Three types:

1. Label change
2. Size change
3. Liquid change

Simulator must:
- Enter CHANGEOVER state
- Block production
- Emit transaction events
- Adjust SKU configuration

---

# 8. CIP Logic

Trigger conditions:

- After 3–4 orders
- After liquid change

Duration:
45 minutes fixed

State:
CIP

Must emit:
- CIPStarted
- CIPEnded

---

# 9. Transaction Events (Governed)

Simulator must emit:

- OrderStarted
- OrderCompleted
- ChangeoverStarted
- ChangeoverCompleted
- CIPStarted
- CIPEnded
- MicrostopStarted
- MicrostopEnded
- StopStarted
- StopEnded
- FaultRaised
- FaultCleared
- BottleCompleted (good/reject)

---

# 10. Architecture Alignment

The simulator must align with:

- ISA-95 object hierarchy
- Telemetry vs Transaction separation
- Monotonic master counters
- Context-attached history
- Topic discipline

---

# 11. Acceptance Criteria

The system is accepted when:

1. Weekly schedule executes fully
2. 3 major breakdowns occur
3. 3 changeovers occur
4. CIP executes at least once
5. Microstops occur randomly
6. Master count remains monotonic
7. Order-level production totals reconcile
8. Historian shows meaningful downtime patterns
9. LLM can query:
   - Top 3 microstops
   - Average fill deviation
   - Breakdown impact
   - Order yield per SKU

---

# 12. Out of Scope

- Full ERP integration
- Full B2MML payload compliance
- Multi-line simulation
- Real PLC integration

---

# 13. Strategic Purpose

This demo will:

- Demonstrate model-driven architecture
- Show why ISA-95 matters
- Enable AI interrogation of contextualized data
- Provide vendor-neutral demonstration platform
- Serve as training foundation for paid courses

---

# End of Scope