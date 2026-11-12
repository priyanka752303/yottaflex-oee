# Design notes: decisions, assumptions, trade-offs

## 1. What the solution does

```
 generator.py ──► input/*.csv ──► calculator.py ──► derived/oee_aggregate.csv
      │                 │                         └► derived/oee_exception.csv  (decision log)
      │                 └──────────► validator.py ──► reports/validation_summary.*
      └► ground_truth/*.csv ──────► evaluate.py  ──► reports/evaluation.*
                                    exporter.py  ──► export/json, export/sql, export/oee.sqlite, manifest.json
```

* **Generator.** Builds master data first, then simulates each machine through the shift calendar. Then it adds micro-stops, production, inspections and counter readings, injects labelled anomalies and assigns deterministic IDs.
* **Calculator.** Reads only `input/`. It never sees `ground_truth/`, so it can't "cheat".
* **Validator.** Checks structure, references, time ordering, lifecycles, duplicates and arithmetic. It also never reads ground truth.
* **Evaluator.** The only module that reads ground truth. It scores the calculator against the anomaly labels and against the simulator's own expected OEE.

## 2. Data model

There are 11 required entities plus 3 supporting tables:

* **`machine_product_standard`.** A bridge table that resolves Machine N:M Product. Each row holds a *versioned* ideal cycle time, valid between `effective_from` and `effective_to`. About 25% of standards get a v2 halfway through the horizon, modelling a process improvement.
* **`shift_break`.** The planned break windows of a shift. Break time is planned downtime by definition, so it lives in its own table rather than being inferred from machine events.
* **`production_order_status_event`.** The append-only lifecycle history `PLANNED → RELEASED → IN_PROGRESS → COMPLETED | CLOSED_SHORT`, plus `CANCELLED`. `production_order.current_status` must equal the latest event, and the validator checks this.
* **`downtime_annotation`.** Records the reason given for each stop. A maintenance engineer's re-annotation supersedes the operator's annotation, and nothing is overwritten.

Other model decisions:

* **History is never overwritten.**
  * Count corrections are new `MANUAL_CORRECTION` rows that point at the original reading (`corrects_count_id`). Re-annotations point at the annotation they supersede.
  * Order status changes are new rows.
  * State events are immutable.
* **Single plant.** The ID convention `SHIFT-2026-01-01-A` has no plant component, so the shift calendar is plant-level and there is one plant. The model still has `plant_id` everywhere, so adding plants only needs a plant prefix in the shift ID.
* **IDs.**
  * Orders are numbered by creation time. That is when an order number is issued in practice, so a later-running order can have a lower number.
  * Events are numbered per machine by start time.
  * Count records are numbered per order by timestamp.
  * IDs are assigned once, after generation, and never re-used.

## 3. OEE rules (the decisions the brief asks to expose)

| Topic | Rule | Why |
|---|---|---|
| Planned production time (PPT) | Shift length − planned stops. Planned stops = break windows from `shift_break`, plus `PLANNED_STOP` events (preventive maintenance, plant closed). | Planned downtime must be explicit and must not depend on what the PLC happened to report. |
| Unscheduled shifts (weekend nights, holiday) | PPT = 0. A, P, Q and OEE are empty, and status is `NOT_SCHEDULED`. | An idle closed plant is not an availability loss. Dividing by zero would only hide that. |
| Downtime that overlaps a break | The part inside the break window counts as planned, and is recorded in `downtime_in_break_s` with a `DOWNTIME_OVERLAPS_BREAK` exception. The rest stays an availability loss. | This avoids double counting the break and keeps the loss visible to maintenance. |
| Micro-stops | A `STOPPED` event shorter than 120 s (`MICRO_STOP_THRESHOLD_S`) is a minor stop. It stays inside run time, so it reduces Performance. | This follows the six-big-losses convention. The threshold is a config value. |
| Changeover | Availability loss (setup). | Common OEE practice. Some plants plan changeovers instead; that would be a one-line change to the reason catalogue. |
| Gaps (no event) | Treated as unplanned stop (`gap_s`) and flagged with `TIME_GAP`. | It is conservative, and the time still reconciles. |
| Overlapping events | Resolved by precedence `PLANNED_STOP > STOPPED > CHANGEOVER > RUNNING`, recorded in `overlap_s`, and flagged as an ERROR. | This is the most conservative reading. The true state can't be known, so a human must review it. |
| Total count | Comes from the PLC counter sequence per order. A reading below the running maximum, with no correction pointing at it, is quarantined. Corrections add their signed adjustment to the *shift of the reading they correct*. | It is robust to spurious readings without double counting, and the original rows stay intact. |
| Ideal cycle time | The **master standard** referenced by the order. If the order's own snapshot disagrees by more than 0.05 s, a `WRONG_IDEAL_CYCLE_TIME` exception is raised. | The master is the governed value. The snapshot is a copy that can be mistyped. |
| Quality | Good = total − scrap − rework (rework is not first-pass good). The values come from `LOT_DISPOSITION` inspections, one per order × shift. `SAMPLE` inspections are informational only. | A lot whose scrap + rework is greater than its counted total is impossible. That disposition is quarantined and the row flagged, not silently capped. |
| Roll-ups | Line and plant rows **sum the components** first, then compute the ratios. They never average machine OEEs. | Averaging ratios gives wrong results when machines have different amounts of time. |
| OEE edge cases | PPT = 0 → empty. A = 0 → OEE 0. No run time or no count → P or Q empty. | Undefined values are never presented as numbers. |

Every row in `oee_aggregate` carries its components, so anyone can recompute A, P, Q and OEE with a calculator. The validator does exactly that, and `python -m oee explain` traces any machine-shift back to its events, readings and dispositions.

## 4. How the synthetic data is made realistic

* **Lines and products.** There are 5 lines, each with its own product family and machine type. Ideal cycle times range from about 4 s (stamping) to about 110 s (milling). Each machine–product pair has its own standard.
* **Machine variation.** Each machine has its own reliability (mean run time between stops of 110–260 min), its own speed loss and its own scrap/rework rates.
* **Shift variation.** The night shift runs about 4% slower and makes about 30% more scrap.
* **Stops.** Stop reasons are drawn by weight: mechanical 45%, electrical 20%, material 20%, quality hold 8%, no operator 7%. Durations are log-normal with reason-specific medians.
* **Orders.** Each order runs for 3–16 h. Actual output varies by −5% to +7% around plan, so both `COMPLETED` and `CLOSED_SHORT` orders occur. About 3% of orders are cancelled, and each machine ends with one released, not-yet-started order.
* **Counter corrections.** 0.4% of counter readings are sensor double-counts that are later fixed by a manual correction.
* **Annotations.** 93% of stops are annotated, with about 88% of operator annotations correct. Engineers re-annotate about 70% of the wrong ones.
* **Exact volumes.** The micro-stop count is calibrated so state events hit the target exactly (100,000). The counter-reading count is calibrated so counts plus inspections hit 500,000 exactly. Smaller scales keep the same per-machine-day densities.

Typical machine-shift KPIs at full scale are in `docs/RESULTS_FULL.md`. Mean OEE is about 74% (p10 65%, p90 83%), availability about 87%, performance about 88% and quality about 98%. The night shift averages about 3 points lower than day shift. That is in the normal range for discrete manufacturing (world class is about 85%).

## 5. Ground truth and evaluation

* **`ground_truth_anomaly`.** One row per injected anomaly, with the record ID, what was changed (original and injected values), the expected detection rule and the expected treatment.
* **`ground_truth_oee`.** Expected machine-shift OEE components, computed by the generator from its own simulated timeline with *separate code* from the calculator. The evaluator compares every machine-shift:
  * All rows without an unresolvable anomaly must match exactly.
  * Rows with an overlapping state or impossible scrap are expected to differ, because the true value can't be known from the data. They are flagged as `EXCEPTION`.
* **`ground_truth_downtime_reason`.** The real stop reason, used to score annotation quality.

Anomalies are injected *after* the clean baseline is built. Each one changes only its own record (and the timeline neighbours it splits). At most one machine-shift-level anomaly lands per machine-shift, so they don't mask each other.

## 6. Reproducibility

* Every random stream is `random.Random(f"{seed}|{purpose}|{key}")`. Python seeds string inputs through SHA-512, so the streams don't depend on `PYTHONHASHSEED`. Each machine and purpose has its own stream, so changing one does not reshuffle the others.
* No wall-clock time appears in any output. Floats are rounded to 6 decimal places before writing.
* `python -m oee repro` runs the full pipeline twice with the same seed and compares the SHA-256 of every output file. It then runs once with seed + 1 to show the data really depends on the seed.
* The SQLite binary is left out of the checksum. Its CSV, JSON and SQL equivalents are covered.

## 7. Trade-offs and limitations

* **Standard library only.** There are no dependencies to install. The downside is plain-Python speed: the full run takes about a minute rather than seconds.
* **Machines run in parallel, not in series.** Line OEE is a roll-up of machines rather than a model of a serial flow line with buffers. A flow-line model would measure line output at the last machine.
* **Simplified state model.** Four machine states are used. Real PLCs have many more (starved, blocked, warm-up). These map onto `STOPPED` plus a reason code.
* **Local time.** Timestamps are local plant time with a fixed offset. India has no DST, but a plant with DST would need UTC storage plus a time-zone conversion.
* **JSON format.** The JSON export is JSON Lines (one object per line), so 440k-row tables can be streamed.
* **Reproducibility scope.** It is guaranteed for the same Python minor version. The underlying `random` algorithms have been stable for years, but CPython does not formally guarantee them across versions.
* **No external data.** No public dataset was used (see `SOURCE_MANIFEST.md`), so the distributions are informed by general domain knowledge, not fitted to real plant data.
