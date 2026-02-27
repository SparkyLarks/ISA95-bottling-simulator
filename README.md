# ISA-95 Bottling Line Simulator
## Amárach StackWorks — Digital Twin Demo v1.0

A realistic ISA-95 aligned bottling line simulator that exposes live telemetry over **Modbus TCP** and stores governed time-series data in a **TimeBase historian** via Node-RED and MQTT.

Built as a vendor-neutral demonstration platform for ISA-95 model-driven architecture, OEE analysis, and AI interrogation of industrial data.

---

## Architecture

```
[Python Simulator]  →  Modbus TCP :502  →  [Node-RED]  →  MQTT  →  [TimeBase Historian]
   Raspberry Pi 2                            Pi 4 (FlowFuse)  MonsterMQ    Pi 5
       |
       └→  logs/transactions.jsonl  (governed event log)
```

### Infrastructure
| Device | Role | IP |
|--------|------|----|
| Raspberry Pi 2 | Python simulator + Modbus TCP server | 192.168.137.4 |
| Raspberry Pi 4 | Node-RED (FlowFuse) + MonsterMQ MQTT broker | 192.168.137.5 |
| Raspberry Pi 5 | TimeBase historian + Grafana | 192.168.137.6 |

---

## Quick Start

```bash
# Install dependencies
pip install openpyxl pyyaml

# Run with defaults (config.yaml)
python main.py

# Run with custom speed
python main.py --speed 2 --port 5020

# Read live registers from a running simulator
python test_registers.py --host 192.168.137.4 --port 502
```

---

## Speed Factor Guide

| `speed_factor` | 1 hour sim = | Full week = | Use for |
|---------------|-------------|-------------|---------|
| 0.5 | 2 hrs wall | ~10 days | Slow demo / fault visibility |
| 1.0 | 1 hr wall | ~5 days | Real-time demo |
| 60 | 1 min wall | ~2 hrs | Development |
| 600 | 6 sec wall | ~12 min | Testing |

Set in `config.yaml` or override: `python main.py --speed 1`

> **Note:** At 1× speed with a 500ms Modbus poll, microstops (5–120 sec) are fully visible.
> At speed_factor > 10, short microstops may be missed between polls.

---

## Historian Tags (35 signals)

All signals are stored in the **TimeBase MCB Bottling Demo** dataset under:

```
historian/Amarach/Crosshaven/Bottling/Line01/{Station}/{signal}/value
```

| Station | Signals |
|---------|---------|
| General | line_state, sku, stop_code, fault_code, line_speed_bpm, good_count, reject_count, order_seq |
| Infeed01 | bottle_presence, infeed_rate_bpm, starved, jam_detected |
| Filler01 | target_weight_g, actual_weight_g, fill_time_ms, scale_stable, drip_sensor |
| Capper01 | torque_target_ncm, torque_actual_ncm, torque_in_spec, cap_feed_ok |
| Checkweigher01 | gross_weight_g, weight_in_spec, rezero_active |
| Labeller01 | label_applied, label_sensor_ok, label_stock_level |
| Scanner01 | barcode_read_ok, rescan_count |
| Labeller02 | hazard_required, hazard_applied, hazard_label_stock |
| RejectPusher01 | reject_triggered, reject_reason, pusher_cycle_ms |

---

## Modbus Register Map

All holding registers. Addresses are **0-indexed**.
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
| 22–23 | 40023–40024 | `actual_weight_g` | float32 | ±0.5% noise |
| 24–25 | 40025–40026 | `fill_time_ms` | uint32 | |
| 26 | 40027 | `scale_stable` | uint16 | False during MS02 |
| 27 | 40028 | `drip_sensor` | uint16 | True during MS03 |
| 29–30 | 40030–40031 | `torque_target_ncm` | float32 | |
| 31–32 | 40032–40033 | `torque_actual_ncm` | float32 | ±1% noise |
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

---

## Stop Code Register Values

| Value | Code | Name | Type |
|-------|------|------|------|
| 0 | — | No stop | |
| 1–10 | MS01–MS10 | Microstops | Machine-derived, not operator-coded |
| 11–20 | ST01–ST10 | Long stops | Operator-coded |
| 21 | BD-M1 | Filler Scale Failure | Major breakdown |
| 22 | BD-M2 | Capper Torque Sensor Failure | Major breakdown |
| 23 | BD-M3 | Checkweigher Loadcell Failure | Major breakdown |

---

## Microstop Intelligence Model

Microstops (3–120 sec) are **machine-derived** — not operator-coded. They are discovered through historian signal correlation, not user input. Each has a signal fingerprint stored in the historian enabling AI/MCP interrogation.

| Code | Name | Key Signals |
|------|------|-------------|
| MS01 | Infeed Misfeed | bottle_presence flicker, infeed_rate drop |
| MS02 | Fill Stabilisation Wait | scale_stable=false, fill_time > expected |
| MS03 | Nozzle Drip Detect | drip_sensor=true, post-fill delay |
| MS04 | Cap Feed Stutter | cap_feed_ok=false, torque absent |
| MS05 | Torque Recheck | torque_in_spec toggles false→true |
| MS06 | Checkweigher Re-zero | rezero_active=true |
| MS07 | Label Peelback | label_sensor_ok toggles |
| MS08 | Barcode Re-scan | barcode_read_ok=false then true |
| MS09 | Reject Pusher Slow Return | pusher_cycle_ms > threshold |
| MS10 | Outfeed Accumulation Nudge | line_speed dip, no fault |

---

## Transaction Events (JSONL)

Written to `logs/transactions.jsonl`. Each line is a valid JSON object per `docs/datacontract.md`.

Event types emitted:
- `StateChanged` — every state transition with signal fingerprint
- `OrderStarted` / `OrderCompleted` — order lifecycle with yield
- `MicrostopStarted` / `MicrostopEnded` — with fingerprint
- `StopStarted` / `StopEnded` — changeovers, CIP, breaks, breakdowns
- `FaultRaised` / `FaultCleared` — major breakdowns
- `CIPStarted` / `CIPEnded`
- `ChangeoverStarted` / `ChangeoverCompleted`
- `BottleCompleted` — sampled at 2% rate

---

## Weekly Schedule Summary

20 production orders across 5 days, 2 shifts/day:
- **4 SKUs** — LEM-500-IE, LEM-200-IE, LEM-2L-IE, COL-500-IE, DC-500-IE
- **3 planned changeovers** (label, size, liquid types)
- **3 major breakdowns** (BD-M1, BD-M2, BD-M3)
- **3+ CIP cycles** (triggered after 3–4 orders and liquid changes)
- **Distributed microstops** across all orders
- **Lunch breaks** and minor breakdowns

---

## File Structure

```
ISA95-bottling-simulator/
├── main.py                         # Entry point
├── config.yaml                     # All tunable parameters
├── test_registers.py               # Live register reader
├── requirements.txt
├── ISA95_Bottling_Line_Model_v1.xlsx  # Master data + schedule
├── logs/
│   └── transactions.jsonl          # Transaction event log
├── docs/
│   ├── datacontract.md             # Telemetry + transaction schemas
│   ├── Scope_of_Work.md            # Project SOW
│   ├── Stop_Reasons.md             # Microstop intelligence model
│   └── State_Machine.md            # Line state machine definition
├── node-red/
│   └── bottling_line_flows.json    # Node-RED flow export
└── simulator/
    ├── config.py                   # Config loader
    ├── register_map.py             # Register addresses + pack/unpack
    ├── modbus_server.py            # Pure-Python Modbus TCP server
    ├── sku_data.py                 # SKU + liquid base definitions
    ├── schedule.py                 # Production schedule loader
    ├── events.py                   # Transaction event emitter
    ├── microstops.py               # MS01–MS10 fingerprints
    ├── breakdowns.py               # BD-M1/M2/M3 definitions
    └── line.py                     # Main simulation engine
```

---

## Node-RED Integration

Node-RED polls Modbus every **500ms**, decodes all 35 signals, and publishes to MQTT.

MQTT topic structure:
```
historian/Amarach/Crosshaven/Bottling/Line01/{Station}/{signal}
```

The TimeBase historian collector subscribes to:
```
historian/Amarach/Crosshaven/Bottling/Line01/#
```

Payload format (UNIX ms timestamp):
```json
{ "timestamp": 1740585946121, "value": 503.83 }
```

---

## Documents

| Document | Description |
|----------|-------------|
| `docs/datacontract.md` | Telemetry and transaction schema definitions |
| `docs/Scope_of_Work.md` | Full project scope and acceptance criteria |
| `docs/Stop_Reasons.md` | Microstop signal fingerprint definitions |
| `docs/State_Machine.md` | Line state machine and transition rules |

---

*Amárach StackWorks — ISA-95 Digital Twin Demo Platform*