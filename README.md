# Bottling Line Modbus Simulator
## Amárach StackWorks — Digital Twin Demo v1.0

A realistic ISA-95 aligned bottling line simulator that exposes live telemetry over **Modbus TCP**
and emits governed transaction events to a **JSONL log file** (Node-RED reads this in Step 4).

---

## Architecture Position

```
[Python Simulator]  →  Modbus TCP  →  [Node-RED]  →  MQTT  →  [TimeBase Historian]
       |
       └→  logs/transactions.jsonl  →  [Node-RED]  →  MQTT  →  [Event Store]
```

The simulator is the **machine**. Node-RED is the **edge integration layer** that will be built in Step 4.

---

## Quick Start

```bash
# Install dependencies (only openpyxl + pyyaml — no pymodbus needed)
pip install openpyxl pyyaml

# Run with defaults (config.yaml, port 502 or 5020 if no root)
python main.py

# Run with custom speed and port
python main.py --speed 60 --port 5020

# Read live registers from a running simulator
python test_registers.py --host 127.0.0.1 --port 5020
```

---

## Speed Factor Guide

| `speed_factor` | 1 hour sim = | Full week = | Use for |
|---------------|-------------|-------------|---------|
| 1.0 | 1 hr wall | ~5 days | Real-time demo |
| 60 | 1 min wall | ~2 hrs | Development |
| 600 | 6 sec wall | ~12 min | Testing |
| 3600 | 1 sec wall | ~2 min | CI/unit tests |

Set in `config.yaml` or override: `python main.py --speed 60`

---

## Modbus Register Map

All holding registers. Addresses are **0-indexed** (Node-RED Modbus node uses 0-indexed).
Documentation addresses = index + 40001.

| Index | Doc Addr | Signal | Type | Notes |
|-------|----------|--------|------|-------|
| 0 | 40001 | `line_state` | uint16 | 0=IDLE, 1=RUNNING, 2=MICROSTOP, 3=STOPPED, 4=FAULT, 5=CHANGEOVER, 6=CIP |
| 1–2 | 40002–40003 | `line_speed_bpm` | float32 | Big-endian IEEE 754 |
| 3–4 | 40004–40005 | `good_count` | uint32 | **Monotonic — never resets** |
| 5–6 | 40006–40007 | `reject_count` | uint32 | **Monotonic — never resets** |
| 7 | 40008 | `order_index` | uint16 | 0-based, 0xFFFF=IDLE |
| 8 | 40009 | `sku_index` | uint16 | 0-based into SKU_LIST, 0xFFFF=IDLE |
| 9 | 40010 | `stop_code` | uint16 | See stop code table |
| 10 | 40011 | `fault_code` | uint16 | 1=BD-M1, 2=BD-M2, 3=BD-M3 |
| 11 | 40012 | `order_seq` | uint16 | Sequential order number |
| 12 | 40013 | `sim_speed×10` | uint16 | speed_factor × 10 |
| 14 | 40015 | `bottle_presence` | uint16 | bool |
| 15–16 | 40016–40017 | `infeed_rate_bpm` | float32 | |
| 17 | 40018 | `starved` | uint16 | bool |
| 18 | 40019 | `jam_detected` | uint16 | bool |
| 20–21 | 40021–40022 | `target_weight_g` | float32 | SKU-dependent |
| 22–23 | 40023–40024 | `actual_weight_g` | float32 | With ±0.5% noise |
| 24–25 | 40025–40026 | `fill_time_ms` | uint32 | |
| 26 | 40027 | `scale_stable` | uint16 | False during MS02 |
| 27 | 40028 | `drip_sensor` | uint16 | True during MS03 |
| 29–30 | 40030–40031 | `torque_target_ncm` | float32 | |
| 31–32 | 40032–40033 | `torque_actual_ncm` | float32 | With ±1% noise |
| 33 | 40034 | `torque_in_spec` | uint16 | False during MS05 |
| 34 | 40035 | `cap_feed_ok` | uint16 | False during MS04 |
| 36–37 | 40037–40038 | `gross_weight_g` | float32 | |
| 38 | 40039 | `weight_in_spec` | uint16 | |
| 39 | 40040 | `rezero_active` | uint16 | True during MS06 / BD-M3 |
| 41 | 40042 | `label_applied` | uint16 | |
| 42 | 40043 | `label_sensor_ok` | uint16 | False during MS07 |
| 43 | 40044 | `label_stock_level` | uint16 | % remaining |
| 45 | 40046 | `barcode_read_ok` | uint16 | False during MS08 |
| 46 | 40047 | `rescan_count` | uint16 | |
| 48 | 40049 | `hazard_label_required` | uint16 | Set by SKU hazard flag |
| 49 | 40050 | `hazard_label_applied` | uint16 | |
| 50 | 40051 | `hazard_label_stock` | uint16 | % |
| 52 | 40053 | `reject_triggered` | uint16 | |
| 53 | 40054 | `reject_reason` | uint16 | 1=weight, 2=torque, 3=barcode, 4=label, 5=hazard |
| 54–55 | 40055–40056 | `pusher_cycle_ms` | uint32 | Elevated during MS09 |

### Float32 decoding in Node-RED
Use the `node-red-contrib-buffer-parser` node with mode `float32be` reading 2 registers.

---

## Stop Code Register Values

| Register Value | Code | Name |
|---------------|------|------|
| 0 | — | No stop |
| 1–10 | MS01–MS10 | Microstops |
| 11–20 | ST01–ST10 | Long stops |
| 21 | BD-M1 | Filler Scale Failure |
| 22 | BD-M2 | Capper Torque Sensor Failure |
| 23 | BD-M3 | Checkweigher Loadcell Failure |

---

## Transaction Events (JSONL)

Written to `logs/transactions.jsonl`. Each line is a valid JSON object per `DATA_CONTRACT.md`.

Event types emitted:
- `StateChanged` — every state transition with fingerprint
- `OrderStarted` / `OrderCompleted` — order lifecycle
- `MicrostopStarted` / `MicrostopEnded` — with signal fingerprint
- `StopStarted` / `StopEnded` — changeovers, CIP, breaks, breakdowns
- `FaultRaised` / `FaultCleared` — major breakdowns
- `CIPStarted` / `CIPEnded`
- `ChangeoverStarted` / `ChangeoverCompleted`
- `BottleCompleted` — sampled at 2% rate to avoid log flooding

---

## Weekly Schedule Summary

20 production orders across 5 days, 2 shifts/day:
- **3 planned changeovers** (label, size, liquid types)
- **3 major breakdowns** (BD-M1 Mon, BD-M2 Mon eve, BD-M3 Tue)
- **3+ CIP cycles** (triggered by order count and liquid changes)
- **Distributed microstops** throughout all production orders
- **Lunch breaks** on Mon and Wed

---

## File Structure

```
bottling_simulator/
├── main.py                    # Entry point
├── config.yaml                # All tunable parameters
├── test_registers.py          # Live register reader
├── requirements.txt
├── logs/
│   └── transactions.jsonl     # Transaction event log (append)
└── simulator/
    ├── config.py              # Config loader
    ├── register_map.py        # Register addresses + pack/unpack
    ├── modbus_server.py       # Pure-Python Modbus TCP server
    ├── sku_data.py            # SKU + liquid base definitions
    ├── schedule.py            # Production schedule
    ├── events.py              # Transaction event emitter
    ├── microstops.py          # MS01–MS10 definitions
    ├── breakdowns.py          # BD-M1/M2/M3 definitions
    └── line.py                # Main simulation engine
```

---

## Node-RED Integration (Step 4 Preview)

The Node-RED flow will:
1. Poll all Modbus registers every 500ms using `node-red-contrib-modbus`
2. Transform to telemetry schema (add `ts`, `q`, `src`, `u`)
3. Publish to MQTT per `DATA_CONTRACT.md` topic structure
4. Watch `logs/transactions.jsonl` for new lines and forward to MQTT

MQTT topic examples:
```
telemetry/Aerogen/Shannon/Bottling/Line01/Filler01/actual_weight_g
telemetry/Aerogen/Shannon/Bottling/Line01/Line01/line_state
transactions/Aerogen/Shannon/Bottling/Line01/StateChanged
```
