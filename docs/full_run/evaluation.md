# Evaluation against ground truth

## Anomaly detection

| Issue type | Injected | Detected | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| OVERLAPPING_STATE | 25 | 25 | 25 | 0 | 0 | 1.0 | 1.0 |
| COUNT_DECREASE_NO_CORRECTION | 25 | 25 | 25 | 0 | 0 | 1.0 | 1.0 |
| SCRAP_EXCEEDS_TOTAL | 25 | 25 | 25 | 0 | 0 | 1.0 | 1.0 |
| WRONG_IDEAL_CYCLE_TIME | 25 | 25 | 25 | 0 | 0 | 1.0 | 1.0 |
| DOWNTIME_OVERLAPS_BREAK | 25 | 25 | 25 | 0 | 0 | 1.0 | 1.0 |

## OEE vs simulation truth

- machine-shifts compared: 8100
- exact match (all 9 components): 8053
- differ because of an unresolvable labelled anomaly: 47
- unexplained mismatches: 0

## Downtime annotation

- stops_requiring_reason: 15427
- annotated: 14342
- unannotated: 1085
- operator_first_annotation_accuracy: 0.8803
- effective_reason_accuracy: 0.964
- re_annotated_by_engineer: 1201

## Data profile (scheduled machine-shifts)

| KPI | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| availability | 0.8651 | 0.7653 | 0.8709 | 0.9595 |
| performance | 0.8812 | 0.84 | 0.8807 | 0.9232 |
| quality | 0.9755 | 0.9618 | 0.9758 | 0.9888 |
| oee | 0.7436 | 0.6506 | 0.7475 | 0.8319 |

OEE mean by line: {"LINE-01": 0.7506, "LINE-02": 0.7391, "LINE-03": 0.7461, "LINE-04": 0.7323, "LINE-05": 0.7502}

Plant OEE mean by shift code: {"A": 0.7547, "B": 0.7454, "C": 0.7215}

Order status: {"CANCELLED": 154, "CLOSED_SHORT": 1941, "COMPLETED": 2773, "IN_PROGRESS": 30, "RELEASED": 30}
