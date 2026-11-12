# Full-scale run results

Command: `python -m oee run --scale full` (seed `20261022`, Python 3.13.5, macOS). The run takes about 49 s and peaks at about 1.25 GB of RAM.
The full dataset (about 520 MB) is not committed. Regenerate it with the command above. Its reports and manifest are copied here:

- [`full_run/validation_summary.md`](full_run/validation_summary.md): 150 of 150 checks pass
- [`full_run/evaluation.md`](full_run/evaluation.md) and [`full_run/evaluation.json`](full_run/evaluation.json): scored against ground truth, plus the data profile
- [`full_run/manifest.json`](full_run/manifest.json): row count and SHA-256 of every file
- [`full_run/reproducibility.json`](full_run/reproducibility.json): output of `python -m oee repro --scale full`

## Volumes

| Table | Rows |
|---|---:|
| line / machine / product | 5 / 30 / 20 |
| machine_product_standard (bridge, versioned) | 157 |
| shift / shift_break | 270 / 482 |
| production_order / status events | 4,928 / 19,335 |
| **state_event** | **100,000** |
| downtime_annotation | 15,543 |
| production_count | 442,969 |
| quality_inspection | 57,031 |
| **count + inspection** | **500,000** |
| oee_aggregate (8,100 machine-shift + 1,350 line-shift + 270 plant-shift) | 9,720 |
| oee_exception | 1,235 |

## Anomaly detection (25 injected per type)

Precision and recall are both **1.0** for all five types, with 0 false positives and 0 misses. The calculator also logged 1,110 `UNANNOTATED_DOWNTIME` items. These are INFO-level operator follow-ups, not injected anomalies.

## OEE accuracy against the simulation

8,100 machine-shifts were compared on 9 components: PPT, run time, total count, good count, ideal time, A, P, Q and OEE.

- **8,053** match exactly.
- **47** differ, and every one contains an overlapping-state or impossible-scrap anomaly. Those rows are flagged `EXCEPTION`, because the true value can't be recovered from the data.
- The remaining 3 of the 50 such machine-shifts match by coincidence. Their quarantined lot truly had 0 scrap and 0 rework, so dropping the disposition gives the true quality.
- **0** mismatches are unexplained.

## Data profile (scheduled machine-shifts)

| KPI | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| Availability | 0.865 | 0.765 | 0.871 | 0.960 |
| Performance | 0.881 | 0.840 | 0.881 | 0.923 |
| Quality | 0.976 | 0.962 | 0.976 | 0.989 |
| OEE | 0.744 | 0.651 | 0.748 | 0.832 |

- **Plant OEE by shift:** A 0.755, B 0.745, C (night) 0.722.
- **Order status:** 2,773 COMPLETED, 1,941 CLOSED_SHORT, 154 CANCELLED, 30 IN_PROGRESS, 30 RELEASED.
- **Annotations:** the operator's first annotation is right 88.0% of the time. After engineer re-annotation (1,201 cases), the effective reason is right 96.4% of the time.

## Reproducibility

`python -m oee repro --scale full` runs the whole pipeline three times. The SQLite file is skipped to save time, which is why this dataset checksum differs from the one in `manifest.json`: that run also wrote `sqlite_load_check.json`.

- **run1 (seed 20261022):** `b30ffde4b1eec51a089c61427f554380768cffb95c8a39b889e18477c87b011f`
- **run2 (seed 20261022):** `b30ffde4b1eec51a089c61427f554380768cffb95c8a39b889e18477c87b011f`. That is byte-identical across all 44 files.
- **run3 (seed 20261023):** `0ba93d6bb847a6f2a2be76ea11c86efd9ecf97deda126bbb49ec546fb31247eb`. That is different, as expected.
