# OEE from machine states, counts and quality: synthetic data and calculation

This repo builds an end-to-end, reproducible workflow:

1. It **generates** linked synthetic manufacturing data: plants, lines, machines, products, versioned ideal cycle times, shift calendars and breaks, production orders with lifecycle history, machine-state events, PLC counter readings with corrections, quality inspections and downtime annotations.
2. It **injects 5 labelled anomaly types** into that data.
3. It **calculates Availability, Performance, Quality and OEE** per machine, line and plant for every shift. Every rule that fires is logged as a decision or exception.
4. It **validates** the result and **evaluates** it against a separate ground truth.

It uses only the Python standard library, so there is nothing to install.

## Quick start

You need Python 3.10 or later (developed and tested on 3.13.5, macOS).

```bash
git clone <this repo> && cd yottaflex-oee

python3 -m oee run --scale starter      # small dataset in ~2 s   -> out/starter/
python3 -m oee run --scale full         # 100k events + 500k count/inspection records in ~1 min -> out/full/
python3 -m unittest discover -s tests -v   # 20 tests (~5 s)
python3 -m oee repro --scale starter    # regenerate twice, compare SHA-256 of every file
python3 -m oee explain --machine MC-001 --shift SHIFT-2026-01-05-A   # trace one OEE row to its source records
```

`make starter | full | test | repro | repro-full | docs` are shortcuts for the same commands. The full run needs about 1.3 GB of RAM and writes about 520 MB, most of it the JSON and SQL exports. Pass `--formats json` or `--formats ""` to write less.

A complete **starter dataset is committed** in [`sample_data/starter/`](sample_data/starter/), so you can look at the outputs without running anything. The SQLite binary is left out.

## What a run produces

```
out/<scale>/
  input/         14 source tables (CSV)          <- the only thing the calculator reads
  derived/       oee_aggregate.csv, oee_exception.csv (decision / exception log)
  ground_truth/  injected anomalies, expected OEE per machine-shift, true stop reasons
  export/        json/*.jsonl, sql/schema.sql + seed.sql, oee.sqlite (FKs enforced)
  reports/       validation_summary.{md,json}, evaluation.{md,json}, sqlite_load_check.json
  manifest.json  seed, scale, command, row count + SHA-256 of every file, dataset checksum
```

## Results (full scale, seed 20261022)

| | |
|---|---|
| Volume | 5 lines, 30 machines, 20 products, 90 days (270 shifts) |
| Records | **100,000** state events and **500,000** count + inspection records (442,969 counts + 57,031 inspections), hit exactly |
| Validation | **150 / 150** checks pass, with 0 foreign-key violations when loaded into SQLite |
| Anomaly detection | 5 types × 25 each: precision **1.0** and recall **1.0** for every type |
| OEE vs simulation truth | **8,053 / 8,100** machine-shifts match exactly. The other 47 contain an unresolvable labelled anomaly and are flagged. **0 unexplained** |
| Reproducibility | The same seed gives byte-identical files; seed + 1 gives different data (see `docs/RESULTS_FULL.md`) |
| Typical KPIs | mean OEE 74% (p10 65%, p90 83%), A 87%, P 88%, Q 98% |

Full numbers are in [`docs/RESULTS_FULL.md`](docs/RESULTS_FULL.md).

## How each requirement is covered

| Brief | Where |
|---|---|
| Master data first, then dependent records with valid parent IDs | `generator.py` steps 1→8. FK checks are in `validator.py` and enforced again by SQLite |
| Shift calendars, ideal cycle times, orders, state transitions, count increments, inspections, scrap/rework, downtime reasons, OEE by shift | `generator.py`, `calculator.py` |
| History persisted, never overwritten | Corrections are new rows with `corrects_count_id`, re-annotations use `supersedes_annotation_id`, and order status changes go to `production_order_status_event` |
| Outcomes from documented rules, not random labels | Order status is derived from counted output, quality from dispositions, and ground truth from the simulation |
| Primary key, foreign keys, cardinality, optionality, effective dates, lifecycles, bridge table | [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md), [`docs/ERD.md`](docs/ERD.md), [`docs/schema.sql`](docs/schema.sql) |
| ID conventions `PO-2026-000001`, `SHIFT-2026-01-01-A`, `EVT-<machine>-000001`, `CNT-<order>-000001`, `QC-2026-000001` | `oee/ids.py`, checked by format validation and a test |
| Step 1: data dictionary (type, required, allowed values, unit, uniqueness, rule) | Generated from `oee/schema.py`, the same source as the DDL and validation |
| Step 4: volume, planned breaks, micro-stops, changeovers, count corrections; fixed seed; one parameterised generator | `config.py` scales `full` / `starter` / `tiny` all use the same generator |
| Step 5: five edge cases, labelled | Overlapping states, count decrease without correction, scrap > total, wrong ideal cycle time, downtime overlapping a break |
| Step 6: derived values from source records | `calculator.py`, which reads `input/` only |
| Step 7: separate ground truth, not leaked | `ground_truth/` is read only by `evaluate.py`, and a test asserts no label column exists in the inputs |
| Step 8: validation | `reports/validation_summary.md`, 150 checks |
| Step 9: CSV, JSON, SQL, README, dictionary, command, seed, manifest, validation summary | `export/`, `manifest.json`, [`SOURCE_MANIFEST.md`](SOURCE_MANIFEST.md) |
| Step 10: regenerate twice and compare checksums | `python -m oee repro` |
| Acceptance: OEE independently recomputable; time reconciles; planned downtime explicit; corrections keep originals | Each one is a validator check *and* a test in `tests/test_pipeline.py` |

## Key decisions (details in [`docs/DESIGN.md`](docs/DESIGN.md))

* **Planned downtime.** Break windows plus `PLANNED_STOP` events are excluded from planned production time. A breakdown that runs into a break is counted as planned *inside* the break and flagged.
* **Micro-stops.** Stops under 120 s stay inside run time and count as a Performance loss. Changeovers count as an Availability loss.
* **Counts.** They come from the PLC counter sequence. A reading below the running maximum, with no correction pointing at it, is quarantined. Corrections are attributed to the shift of the reading they fix.
* **Ideal cycle time.** It comes from the governed master standard, and a disagreeing order snapshot is flagged.
* **Line and plant OEE.** These sum the time and count components first, then divide. They never average ratios.
* **Undefined values.** These stay empty rather than becoming 0 or 100% (unscheduled shifts are marked `NOT_SCHEDULED`).

## Repository layout

```
oee/
  config.py       scales, seed, thresholds (all assumptions in one place)
  schema.py       every table and field -> docs, DDL and validation
  ids.py          ID builders and patterns, timestamp helpers
  generator.py    synthetic data and anomaly injection and simulation ground truth
  calculator.py   OEE calculation and exception log (input tables only)
  validator.py    structural, temporal, lifecycle, duplicate and reconciliation checks
  evaluate.py     scores against ground truth, data profile
  exporter.py     JSONL, SQL, SQLite, manifest, generated docs
  __main__.py     CLI: run | repro | explain | docs
tests/            rule unit tests + end-to-end tests
docs/             DESIGN.md, DATA_DICTIONARY.md, ERD.md, schema.sql, RESULTS_FULL.md
sample_data/      committed starter dataset
prompts/          AI prompt history
AI_USAGE.md       how AI was used and how the output was verified
```

## Limitations

The model is a single plant, with machines running in parallel rather than in series, four machine states and fixed-offset local time. The full list is in [`docs/DESIGN.md` §7](docs/DESIGN.md#7-trade-offs-and-limitations).
