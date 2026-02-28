# DATA_CONTRACT.md
## Bottling Line Demo — Telemetry + Transaction Data Contracts (Phase 1)

**Project:** Bottling Line Digital Twin & MDEA Demo  
**Version:** 1.0  
**Date:** 2026-02-26  
**Purpose:** Lock schemas so Cursor + MCP + humans don’t drift.

---

# 0) Core Rules

1. **Two planes only in Phase 1:**
   - Telemetry (high-rate): “what’s happening”
   - Transactions (low-rate): “what happened” (facts)

2. **Master counts are monotonic and never reset.**

3. **Telemetry is never rejected** (it may be marked bad quality and routed).

4. **Transactions can be rejected** if schema/validation fails.

5. **All topics encode ISA-95 physical hierarchy** where possible:
   - enterprise/site/area/line (and station/cell if relevant)

---

# 1) Topic Contracts

## 1.1 Telemetry Topics (Plane 1)
Root:

telemetry/{enterprise}/{site}/{area}/{line}/{station}/{signal}


Examples:

telemetry/Amarach/Crosshaven/Shannon/Bottling/Line01/Filler01/actual_weight_g
telemetry/Amarach/Crosshaven//Shannon/Bottling/Line01/Line01/line_speed_bpm
telemetry/Amarach/Crosshaven/Shannon/Bottling/Line01/Capper01/torque_actual_ncm


Notes:
- `{station}` may be `Line01` for line-level signals.
- Keep payload small; do not embed full context objects repeatedly.

---

## 1.2 Transaction Topics (Plane 2)
Root:

transactions/{enterprise}/{site}/{area}/{line}/{eventType}


Examples:

transactions/Amarach/CrosshavenBottling/Line01/OrderStarted
transactions/Amarach/Crosshaven/Bottling/Line01/MicrostopStarted
transactions/Amarach/Crosshaven/Bottling/Line01/BottleCompleted


---

# 2) Telemetry Payload Schema (Phase 1)

Telemetry is flat, minimal, and cheap.

## 2.1 Required Fields (All Telemetry)
| Field | Type | Required | Notes |
|------|------|----------|------|
| ts | string (ISO8601) | Yes | UTC ISO string |
| v | number / boolean / string | Yes | Value |
| q | string | Yes | `GOOD` / `BAD` / `UNCERTAIN` |
| src | string | No | `sim` / `plc` / `derived` |
| u | string | No | Units (e.g., `g`, `bpm`, `ncm`) |

## 2.2 Example Telemetry Message
```json
{
  "ts": "2026-02-26T12:34:56.789Z",
  "v": 501.2,
  "q": "GOOD",
  "src": "sim",
  "u": "g"
}
2.3 Telemetry Quality Rules

If missing ts or v: set q="BAD" and route to:

telemetry_invalid/{enterprise}/{site}/{area}/{line}/...
3) Transaction Payload Schema (Phase 1)

Transactions are verbose, auditable, and governed.

3.1 Required Fields (All Transactions)
Field	Type	Required	Notes
eventType	string	Yes	Must match topic tail
eventId	string	Yes	UUID/ULID
ts	string (ISO8601)	Yes	UTC ISO
enterprise	string	Yes	e.g. Amarach
site	string	Yes	e.g. Crosshaven
area	string	Yes	e.g. Bottling
line	string	Yes	e.g. Line01
orderId	string/null	Yes	null allowed when IDLE
sku	string/null	Yes	null allowed when IDLE
actor	object	Yes	Who/what caused it
validation	object	Yes	status + version
actor object
Field	Type	Required	Notes
type	string	Yes	sim / operator / system
id	string	Yes	simulator instance, operator id, etc
validation object
Field	Type	Required	Notes
status	string	Yes	ACCEPTED / REJECTED
version	string	Yes	e.g. v1
reasons	array	No	rejection reasons
4) State Change Events
4.1 StateChanged (required)

Topic:

transactions/.../StateChanged

Payload additions:

Field	Type	Required
fromState	string	Yes
toState	string	Yes
stopCode	string/null	No
faultCode	string/null	No
reasonId	integer/null	No
durationMs	integer/null	No
fingerprint	object/null	No

Example:

{
  "eventType":"StateChanged",
  "eventId":"01HS...ULID",
  "ts":"2026-02-26T12:00:00.000Z",
  "enterprise":"Aerogen",
  "site":"Shannon",
  "area":"Bottling",
  "line":"Line01",
  "orderId":"ORD-0003",
  "sku":"COL-500-IE",
  "actor":{"type":"system","id":"sim01"},
  "validation":{"status":"ACCEPTED","version":"v1"},
  "fromState":"RUNNING",
  "toState":"MICROSTOP",
  "stopCode":"MS02",
  "fingerprint":{"scale_stable":"false","fill_time_delta_ms":950}
}
5) Order Lifecycle Transactions
5.1 OrderStarted

Required additions:

orderId (non-null)

sku (non-null)

plannedQty (int)

plannedStartTs (ISO)

plannedEndTs (ISO, optional)

5.2 OrderCompleted

Required additions:

goodCountDelta (int)

rejectCountDelta (int)

durationMs (int)

yield (float)

6) BottleCompleted Transaction

Topic:

transactions/.../BottleCompleted

Required additions:

Field	Type	Required
result	string	Yes
station	string	Yes
rejectReason	string/null	No
weight	number/null	No
torque	number/null	No
7) Stops, Microstops, and Faults
7.1 MicrostopStarted / MicrostopEnded

Additions:

stopCode (MSxx)

fingerprint (object)

durationMs (on Ended)

7.2 StopStarted / StopEnded (Long stops)

Additions:

stopCode (STxx, BD-xx)

reasonId (operator-coded numeric, optional)

reasonText (optional)

durationMs (on Ended)

7.3 FaultRaised / FaultCleared

Additions:

faultCode (string)

severity (Minor/Major)

station (string)

8) Rejection Handling (Transactions)

If a transaction fails validation:

publish:

transactions/.../TransactionRejected

include:

rejectedEventType

rejectedEventId

reasons[]

Telemetry is never rejected; it is flagged by q.

9) Idempotency / Deduplication

Transactions must be idempotent by eventId.
Consumers must deduplicate by storing last N ids per line.

Telemetry may be retained for “last-known” signals if desired, but avoid retaining high-rate streams.

10) Versioning

All transactions include:

validation.version
Optionally include:

schemaVersion

When schemaVersion changes:

increment v1 → v2

maintain backward compatibility where possible