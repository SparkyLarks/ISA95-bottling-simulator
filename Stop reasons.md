ou’re defining two parallel realities:

Operator-visible reason codes → longer stops → tablet input → explicit ReasonID

Machine-derived microstops → not recorded → inferred from signal patterns → revealed via historian + MCP

That’s powerful. It mirrors real plants.

Below is a structured description of each microstop:

What it is physically

What actually happens on the machine

What signals reveal it

How it is detected from historian data

How MCP/LLM could surface it

You can paste this directly into your design doc.

Microstop Intelligence Model
Machine-Derived (Not Operator-Coded)

Microstops are short interruptions (3–120 sec) that:

Do not trigger formal downtime reporting

May not latch a fault

Often resolve automatically

Accumulate significant hidden loss

They are discovered through signal correlation, not user input.

MS01 – Infeed Misfeed
What It Is (Physical Reality)

A bottle fails to enter correctly.
Bottle tips, misaligns, or hesitates in starwheel.

Operator may tap the bottle or nudge it.

What Happens on Machine

Conveyor slows briefly

Bottle presence sensor flickers

No fill cycle starts

Signals Involved

bottle_presence

infeed_rate_bpm

line_speed_bpm

fill_cycle_start flag

Historian Detection Pattern

Condition:

bottle_presence toggles rapidly (0→1→0)

infeed_rate drops > 30%

no fill cycle begins for 5–25 sec

no fault latched

Group Logic:

bottle_presence flicker
AND line_speed_bpm < nominal
AND no Generator_On or fill_start
FOR 5–25 sec
How MCP Reveals It

Cluster short speed dips at Infeed01
Group by duration + absence of fault
Label recurring pattern = MS01

MS02 – Fill Stabilisation Wait
Physical Reality

Scale does not stabilise quickly.
Foaming, vibration, or density variation.

What Happens

Fill starts

Scale_stable remains false

Fill completion delayed

Signals

scale_stable

fill_time_ms

target_weight

actual_weight

Historian Pattern

Condition:

fill_start occurs

scale_stable = false for > threshold

fill_time > theoretical time by >15%

no fault bit set

Group Logic:

scale_stable = false
AND fill_time > expected
AND torque not yet active
MCP Use

LLM can:

Compare fill_time vs expected based on volume

Identify recurring delays

Correlate to specific SKU or bottle size

MS03 – Nozzle Drip Detect
Physical Reality

Product drips after fill.
Machine pauses briefly to avoid contamination.

Signals

drip_sensor

fill_complete flag

post_fill_delay

Historian Detection

drip_sensor = true

fill_complete achieved

next station delayed 5–20 sec

Pattern:

drip_sensor=1
AND post_fill_delay > baseline
MS04 – Cap Feed Stutter
Physical Reality

Cap chute hesitates.
Capper pauses to wait for next cap.

Signals

cap_feed_ok

torque_actual missing

capper motor current spike

Historian Pattern:

cap_feed_ok = false
AND torque measurement missing for 1 cycle
AND line_speed dip 10–50 sec
MS05 – Torque Recheck
Physical Reality

Torque initially out of range.
System retightens or re-measures.

Signals

torque_actual

torque_in_spec

reject_flag

Historian Pattern:

torque_in_spec = false
FOLLOWED BY torque_in_spec = true
WITHIN 60 sec
AND no reject count increment

Reveals hidden quality instability.

MS06 – Checkweigher Re-zero
Physical Reality

Load cell drift.
Machine pauses to re-zero scale.

Signals

rezero_active

weight_signal

weight_in_spec

Historian Pattern:

rezero_active = true
AND line_state=MICROSTOP
FOR 10–90 sec
MS07 – Label Peelback
Physical Reality

Label not adhering properly.
Sensor flickers.

Signals

label_sensor_ok

reject rate spike

Pattern:

label_sensor_ok toggles
AND reject rate slightly elevated
AND no full stop
MS08 – Barcode Re-scan
Physical Reality

Barcode not read first attempt.
Scanner retries.

Signals

barcode_read_ok

rescan_count

Pattern:

barcode_read_ok = false
FOLLOWED BY success
WITHIN 30 sec
AND no reject increment
MS09 – Reject Pusher Slow Return
Physical Reality

Reject actuator slow to retract.
Line pauses briefly.

Signals

pusher_cycle_time_ms

reject_triggered

Pattern:

pusher_cycle_time_ms > threshold
AND line_speed dip
MS10 – Outfeed Accumulation Nudge
Physical Reality

Downstream buffer near full.
Operator nudges accumulation.

Signals

outfeed_full near threshold

conveyor speed drop

Pattern:

outfeed_full near 1
AND line_speed_bpm dips
WITHOUT fault latch
Architectural Insight

Microstops are:

Derived events

Inferred from signal groupings

Discovered through historian correlation

Not operator-coded

Longer stops are:

Explicitly coded

Often fault-latched

Sometimes operator-entered

How This Fits Your Demo

Operator tablet:

Records ST01–ST10 and breakdowns

Historian:

Reveals MS01–MS10

MCP Layer:

Clusters signal patterns

Groups recurring dips

Maps them to derived microstop categories

Surfaces hidden loss

The demo user sees:

"Availability = 87%"

The AI layer reveals:

"22% of your hidden loss is Fill Stabilisation microstops on 2L SKU."

That’s the power moment.