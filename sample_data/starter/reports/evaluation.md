# Evaluation against ground truth

## Anomaly detection

| Issue type | Injected | Detected | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| OVERLAPPING_STATE | 3 | 3 | 3 | 0 | 0 | 1.0 | 1.0 |
| COUNT_DECREASE_NO_CORRECTION | 3 | 3 | 3 | 0 | 0 | 1.0 | 1.0 |
| SCRAP_EXCEEDS_TOTAL | 3 | 3 | 3 | 0 | 0 | 1.0 | 1.0 |
| WRONG_IDEAL_CYCLE_TIME | 3 | 3 | 3 | 0 | 0 | 1.0 | 1.0 |
| DOWNTIME_OVERLAPS_BREAK | 3 | 3 | 3 | 0 | 0 | 1.0 | 1.0 |

## OEE vs simulation truth

- machine-shifts compared: 252
- exact match (all 9 components): 246
- differ because of an unresolvable labelled anomaly: 6
- unexplained mismatches: 0

## Downtime annotation

- stops_requiring_reason: 575
- annotated: 529
- unannotated: 46
- operator_first_annotation_accuracy: 0.8809
- effective_reason_accuracy: 0.9603
- re_annotated_by_engineer: 42

## Data profile (scheduled machine-shifts)

| KPI | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| availability | 0.8544 | 0.7477 | 0.8607 | 0.9478 |
| performance | 0.8692 | 0.8279 | 0.8691 | 0.9096 |
| quality | 0.9787 | 0.9668 | 0.9784 | 0.9902 |
| oee | 0.7264 | 0.6451 | 0.7298 | 0.8129 |

OEE mean by line: {"LINE-01": 0.7325, "LINE-02": 0.7213}

Plant OEE mean by shift code: {"A": 0.7284, "B": 0.7353, "C": 0.7112}

Order status: {"CANCELLED": 2, "CLOSED_SHORT": 56, "COMPLETED": 97, "IN_PROGRESS": 6, "RELEASED": 6}
