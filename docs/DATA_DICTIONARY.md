# Data dictionary

Generated from `oee/schema.py` (`python -m oee docs`). The same definitions drive the SQL DDL and the structural validation, so this document cannot drift from the code.

Conventions: timestamps are ISO-8601 local plant time with offset (`+05:30`, Asia/Kolkata); intervals are half-open `[start, end)`; durations are integer seconds; empty CSV cell = null.

## Input (source) tables

### `plant` - Plant

Manufacturing site. Owns the shift calendar.

- Grain: one row per plant
- Primary key: `plant_id`
- Lifecycle: ACTIVE -> INACTIVE
- Effective dating: effective_from

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `plant_id` | STRING | Y | `^PLT-\d{2}$` |  | Y |  | Plant identifier |
| `plant_name` | STRING | Y |  |  |  |  | Display name |
| `timezone` | STRING | Y | Asia/Kolkata |  |  |  | IANA time zone of all local timestamps |
| `country_code` | STRING | Y | `^[A-Z]{2}$` |  |  |  | ISO 3166-1 alpha-2 |
| `status` | STRING | Y | ACTIVE, INACTIVE |  |  |  |  |
| `effective_from` | DATE | Y |  |  |  |  | Date the plant record became valid |

### `line` - Line

Production line inside a plant; one product family per line.

- Grain: one row per line
- Primary key: `line_id`
- Lifecycle: ACTIVE -> INACTIVE
- Effective dating: effective_from

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `line_id` | STRING | Y | `^LINE-\d{2}$` |  | Y |  |  |
| `plant_id` | STRING | Y |  |  |  | plant.plant_id |  |
| `line_name` | STRING | Y |  |  |  |  |  |
| `product_family` | STRING | Y |  |  |  |  | Family of products the line is qualified for |
| `status` | STRING | Y | ACTIVE, INACTIVE |  |  |  |  |
| `effective_from` | DATE | Y |  |  |  |  |  |

### `machine` - Machine

Asset that emits state events and part counts.

- Grain: one row per machine
- Primary key: `machine_id`
- Lifecycle: ACTIVE <-> MAINTENANCE -> DECOMMISSIONED
- Effective dating: effective_from

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `machine_id` | STRING | Y | `^MC-\d{3}$` |  | Y |  |  |
| `line_id` | STRING | Y |  |  |  | line.line_id |  |
| `machine_name` | STRING | Y |  |  |  |  |  |
| `machine_type` | STRING | Y | CNC_MILL, CNC_LATHE, INJECTION_MOLDER, STAMPING_PRESS, GRINDER |  |  |  |  |
| `position_in_line` | INTEGER | Y |  |  |  |  | >= 1, unique within line |
| `commissioned_date` | DATE | Y |  |  |  |  | <= effective_from of any standard |
| `status` | STRING | Y | ACTIVE, MAINTENANCE, DECOMMISSIONED |  |  |  |  |
| `effective_from` | DATE | Y |  |  |  |  |  |

### `product` - Product

Part number that can be produced.

- Grain: one row per product
- Primary key: `product_id`
- Lifecycle: ACTIVE -> OBSOLETE
- Effective dating: effective_from

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `product_id` | STRING | Y | `^PRD-\d{3}$` |  | Y |  |  |
| `product_name` | STRING | Y |  |  |  |  |  |
| `product_family` | STRING | Y |  |  |  |  | matches the family of every line that makes it |
| `unit_of_measure` | STRING | Y | EA |  |  |  |  |
| `status` | STRING | Y | ACTIVE, OBSOLETE |  |  |  |  |
| `effective_from` | DATE | Y |  |  |  |  |  |

### `machine_product_standard` - Ideal cycle time (Machine x Product bridge)

Bridge table resolving Machine N:M Product. Holds the versioned ideal cycle time used for Performance.

- Grain: one row per machine, product and version
- Primary key: `standard_id`
- Effective dating: effective_from / effective_to (half-open interval)

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `standard_id` | STRING | Y | `^STD-MC-\d{3}-PRD-\d{3}-V\d+$` |  | Y |  |  |
| `machine_id` | STRING | Y |  |  |  | machine.machine_id |  |
| `product_id` | STRING | Y |  |  |  | product.product_id |  |
| `version` | INTEGER | Y |  |  |  |  | >= 1, consecutive per machine+product |
| `ideal_cycle_time_s` | DECIMAL | Y |  | seconds per unit |  |  | > 0 |
| `effective_from` | TIMESTAMP | Y |  |  |  |  | versions of one machine+product do not overlap |
| `effective_to` | TIMESTAMP | N |  |  |  |  | > effective_from; empty = open-ended |
| `approved_by_role` | STRING | Y | PLANT_OPERATOR, MAINTENANCE_ENGINEER, QUALITY_ENGINEER, PRODUCTION_PLANNER, OT_IT_ADMINISTRATOR |  |  |  |  |

### `downtime_reason` - DowntimeReason

Reason code catalogue and its OEE treatment.

- Grain: one row per reason code
- Primary key: `reason_code`
- Effective dating: effective_from

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `reason_code` | STRING | Y | `^DR-[A-Z]+(-[A-Z]+)?$` |  | Y |  |  |
| `description` | STRING | Y |  |  |  |  |  |
| `category` | STRING | Y | PLANNED_STOP, UNPLANNED_STOP, SETUP, MINOR_STOP, UNKNOWN |  |  |  |  |
| `oee_loss_bucket` | STRING | Y | NONE, AVAILABILITY, PERFORMANCE |  |  |  | Where the time lands in OEE. NONE = excluded from planned production time |
| `is_planned` | BOOLEAN | Y |  |  |  |  |  |
| `requires_annotation` | BOOLEAN | Y |  |  |  |  | Operator must give a reason for this kind of stop |
| `effective_from` | DATE | Y |  |  |  |  |  |

### `shift` - Shift

Plant shift calendar instance (date + shift code).

- Grain: one row per plant, date and shift code
- Primary key: `shift_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `shift_id` | STRING | Y | `^SHIFT-\d{4}-\d{2}-\d{2}-[ABC]$` |  | Y |  |  |
| `plant_id` | STRING | Y |  |  |  | plant.plant_id |  |
| `shift_date` | DATE | Y |  |  |  |  | date on which the shift starts |
| `shift_code` | STRING | Y | A, B, C |  |  |  |  |
| `start_ts` | TIMESTAMP | Y |  |  |  |  |  |
| `end_ts` | TIMESTAMP | Y |  |  |  |  | > start_ts; shifts of a plant are contiguous and do not overlap |
| `duration_s` | INTEGER | Y |  | seconds |  |  | = end_ts - start_ts |
| `is_production_scheduled` | BOOLEAN | Y |  |  |  |  | false = plant closed (weekend night / holiday) |
| `calendar_note` | STRING | N | WEEKEND_NIGHT, HOLIDAY |  |  |  |  |

### `shift_break` - Planned break (child of Shift)

Planned break window. Always planned downtime, whatever the machine reports.

- Grain: one row per break window
- Primary key: `break_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `break_id` | STRING | Y | `^BRK-\d{4}-\d{2}-\d{2}-[ABC]-\d$` |  | Y |  |  |
| `shift_id` | STRING | Y |  |  |  | shift.shift_id |  |
| `break_type` | STRING | Y | TEA, MEAL |  |  |  |  |
| `start_ts` | TIMESTAMP | Y |  |  |  |  | >= shift.start_ts |
| `end_ts` | TIMESTAMP | Y |  |  |  |  | <= shift.end_ts and > start_ts |
| `duration_s` | INTEGER | Y |  | seconds |  |  | = end_ts - start_ts |

### `production_order` - ProductionOrder

Work order to make a product on one machine.

- Grain: one row per order
- Primary key: `order_id`
- Lifecycle: PLANNED -> RELEASED -> IN_PROGRESS -> COMPLETED | CLOSED_SHORT; PLANNED/RELEASED -> CANCELLED

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `order_id` | STRING | Y | `^PO-2026-\d{6}$` |  | Y |  |  |
| `product_id` | STRING | Y |  |  |  | product.product_id |  |
| `machine_id` | STRING | Y |  |  |  | machine.machine_id |  |
| `standard_id` | STRING | Y |  |  |  | machine_product_standard.standard_id | same machine+product; effective at released_ts |
| `ideal_cycle_time_s` | DECIMAL | Y |  | seconds per unit |  |  | snapshot copied from the standard at release; must equal it (+/- 0.05 s) |
| `planned_qty` | INTEGER | Y |  | units |  |  | > 0 |
| `planned_start_ts` | TIMESTAMP | Y |  |  |  |  |  |
| `planned_end_ts` | TIMESTAMP | Y |  |  |  |  | > planned_start_ts |
| `created_ts` | TIMESTAMP | Y |  |  |  |  | <= released_ts |
| `released_ts` | TIMESTAMP | N |  |  |  |  |  |
| `actual_start_ts` | TIMESTAMP | N |  |  |  |  | >= released_ts |
| `actual_end_ts` | TIMESTAMP | N |  |  |  |  | >= actual_start_ts |
| `current_status` | STRING | Y | PLANNED, RELEASED, IN_PROGRESS, COMPLETED, CLOSED_SHORT, CANCELLED |  |  |  | = to_status of the latest status event |

### `production_order_status_event` - ProductionOrder lifecycle history

Append-only history of order status changes (history is never overwritten).

- Grain: one row per status change
- Primary key: `status_event_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `status_event_id` | STRING | Y | `^POS-2026-\d{6}-\d{2}$` |  | Y |  |  |
| `order_id` | STRING | Y |  |  |  | production_order.order_id |  |
| `from_status` | STRING | N | PLANNED, RELEASED, IN_PROGRESS, COMPLETED, CLOSED_SHORT, CANCELLED |  |  |  |  |
| `to_status` | STRING | Y | PLANNED, RELEASED, IN_PROGRESS, COMPLETED, CLOSED_SHORT, CANCELLED |  |  |  | allowed transition from from_status |
| `changed_ts` | TIMESTAMP | Y |  |  |  |  | non-decreasing within an order |
| `changed_by_role` | STRING | Y | PLANT_OPERATOR, MAINTENANCE_ENGINEER, QUALITY_ENGINEER, PRODUCTION_PLANNER, OT_IT_ADMINISTRATOR |  |  |  |  |

### `state_event` - StateEvent

Machine state interval from PLC/MES. Split at shift boundaries. Never updated after insert.

- Grain: one row per machine state interval
- Primary key: `event_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `event_id` | STRING | Y | `^EVT-MC-\d{3}-\d{6}$` |  | Y |  | EVT-<machine-id>-<seq>, seq ordered by start_ts |
| `machine_id` | STRING | Y |  |  |  | machine.machine_id |  |
| `shift_id` | STRING | Y |  |  |  | shift.shift_id | event lies inside the shift window |
| `state` | STRING | Y | RUNNING, STOPPED, CHANGEOVER, PLANNED_STOP |  |  |  |  |
| `start_ts` | TIMESTAMP | Y |  |  |  |  |  |
| `end_ts` | TIMESTAMP | Y |  |  |  |  | > start_ts |
| `duration_s` | INTEGER | Y |  | seconds |  |  | = end_ts - start_ts |
| `reason_code` | STRING | N |  |  |  | downtime_reason.reason_code | empty only for RUNNING; DR-UNASSIGNED until annotated |
| `order_id` | STRING | N |  |  |  | production_order.order_id | required for RUNNING and CHANGEOVER |
| `source` | STRING | Y | PLC, MES |  |  |  |  |

### `downtime_annotation` - Downtime reason annotation

Append-only reason assignment for a stop. A later annotation supersedes an earlier one.

- Grain: one row per annotation
- Primary key: `annotation_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `annotation_id` | STRING | Y | `^ANN-2026-\d{6}$` |  | Y |  |  |
| `event_id` | STRING | Y |  |  |  | state_event.event_id | event is STOPPED |
| `reason_code` | STRING | Y |  |  |  | downtime_reason.reason_code |  |
| `annotated_by_role` | STRING | Y | PLANT_OPERATOR, MAINTENANCE_ENGINEER, QUALITY_ENGINEER, PRODUCTION_PLANNER, OT_IT_ADMINISTRATOR |  |  |  |  |
| `annotated_ts` | TIMESTAMP | Y |  |  |  |  | >= event end_ts |
| `supersedes_annotation_id` | STRING | N |  |  |  | downtime_annotation.annotation_id | same event_id; earlier annotated_ts |

### `production_count` - ProductionCount

PLC counter readings (cumulative per order) plus manual corrections. Originals are never edited.

- Grain: one row per counter reading or correction
- Primary key: `count_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `count_id` | STRING | Y | `^CNT-PO-2026-\d{6}-\d{6}$` |  | Y |  | CNT-<order-id>-<seq>, seq ordered by record_ts |
| `order_id` | STRING | Y |  |  |  | production_order.order_id |  |
| `machine_id` | STRING | Y |  |  |  | machine.machine_id | = production_order.machine_id |
| `shift_id` | STRING | Y |  |  |  | shift.shift_id | reading: shift containing record_ts; correction: shift of the corrected reading |
| `record_ts` | TIMESTAMP | Y |  |  |  |  |  |
| `record_type` | STRING | Y | PLC_READING, MANUAL_CORRECTION |  |  |  |  |
| `counter_value` | INTEGER | N |  | units |  |  | PLC_READING only; cumulative since order start; must not decrease |
| `increment_qty` | INTEGER | Y |  | units |  |  | reading: counter_value - previous valid reading; correction: signed adjustment |
| `corrects_count_id` | STRING | N |  |  |  | production_count.count_id | MANUAL_CORRECTION only; points at the original reading |
| `correction_reason` | STRING | N | SENSOR_DOUBLE_COUNT, COUNTER_RESET |  |  |  |  |
| `entered_by_role` | STRING | Y | PLANT_OPERATOR, MAINTENANCE_ENGINEER, QUALITY_ENGINEER, PRODUCTION_PLANNER, OT_IT_ADMINISTRATOR |  |  |  |  |

### `quality_inspection` - QualityInspection

SAMPLE = periodic in-process check (informational). LOT_DISPOSITION = scrap/rework decision for the units of one order made in one shift (feeds Quality).

- Grain: one row per inspection
- Primary key: `inspection_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `inspection_id` | STRING | Y | `^QC-2026-\d{6}$` |  | Y |  |  |
| `inspection_type` | STRING | Y | SAMPLE, LOT_DISPOSITION |  |  |  |  |
| `order_id` | STRING | Y |  |  |  | production_order.order_id |  |
| `machine_id` | STRING | Y |  |  |  | machine.machine_id |  |
| `shift_id` | STRING | Y |  |  |  | shift.shift_id | shift whose output is inspected |
| `inspection_ts` | TIMESTAMP | Y |  |  |  |  |  |
| `sample_size` | INTEGER | N |  | units |  |  | SAMPLE only; > 0 |
| `defects_found` | INTEGER | N |  | units |  |  | SAMPLE only; <= sample_size |
| `inspected_qty` | INTEGER | N |  | units |  |  | LOT_DISPOSITION only; = counted total |
| `scrap_qty` | INTEGER | N |  | units |  |  | LOT_DISPOSITION only; scrap+rework <= total |
| `rework_qty` | INTEGER | N |  | units |  |  | LOT_DISPOSITION only |
| `result` | STRING | Y | PASS, FAIL, DISPOSITIONED |  |  |  |  |
| `inspector_role` | STRING | Y | PLANT_OPERATOR, MAINTENANCE_ENGINEER, QUALITY_ENGINEER, PRODUCTION_PLANNER, OT_IT_ADMINISTRATOR |  |  |  |  |

## Derived tables

### `oee_aggregate` - OEEAggregate

OEE and its time/count components, computed only from input tables. Line and plant rows are time/count-weighted roll-ups, never averages of ratios.

- Grain: one row per (machine|line|plant) and shift
- Primary key: `aggregate_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `aggregate_id` | STRING | Y | `^OEE-(MS|LS|PS)-[A-Z0-9-]+$` |  | Y |  |  |
| `aggregate_level` | STRING | Y | MACHINE_SHIFT, LINE_SHIFT, PLANT_SHIFT |  |  |  |  |
| `plant_id` | STRING | Y |  |  |  | plant.plant_id |  |
| `line_id` | STRING | N |  |  |  | line.line_id |  |
| `machine_id` | STRING | N |  |  |  | machine.machine_id |  |
| `shift_id` | STRING | Y |  |  |  | shift.shift_id |  |
| `shift_duration_s` | INTEGER | Y |  | seconds |  |  |  |
| `planned_stop_s` | INTEGER | Y |  | seconds |  |  | Breaks + planned stops (excluded from planned production time) |
| `planned_production_time_s` | INTEGER | Y |  | seconds |  |  | = shift_duration_s - planned_stop_s |
| `unplanned_stop_s` | INTEGER | Y |  | seconds |  |  | Stops >= micro-stop threshold and changeovers, outside breaks |
| `minor_stop_s` | INTEGER | Y |  | seconds |  |  | Stops < threshold; part of run time (performance loss) |
| `gap_s` | INTEGER | Y |  | seconds |  |  | Time with no state event; treated as unplanned stop |
| `overlap_s` | INTEGER | Y |  | seconds |  |  | Time covered by >1 event (resolved by precedence) |
| `downtime_in_break_s` | INTEGER | Y |  | seconds |  |  | Stop time reported inside a break (reclassified as planned) |
| `running_s` | INTEGER | Y |  | seconds |  |  |  |
| `run_time_s` | INTEGER | Y |  | seconds |  |  | = running_s + minor_stop_s = PPT - unplanned_stop_s - gap_s |
| `total_count` | INTEGER | Y |  | units |  |  |  |
| `scrap_count` | INTEGER | Y |  | units |  |  |  |
| `rework_count` | INTEGER | Y |  | units |  |  |  |
| `good_count` | INTEGER | Y |  | units |  |  | = total - scrap - rework |
| `ideal_run_time_s` | DECIMAL | Y |  | seconds |  |  | = sum(total per order x standard ideal cycle time) |
| `availability` | DECIMAL | N |  |  |  |  | run_time / PPT |
| `performance` | DECIMAL | N |  |  |  |  | ideal_run_time / run_time |
| `quality` | DECIMAL | N |  |  |  |  | good / total |
| `oee` | DECIMAL | N |  |  |  |  | availability x performance x quality |
| `data_quality_status` | STRING | Y | CLEAN, EXCEPTION, NOT_SCHEDULED |  |  |  |  |
| `exception_codes` | STRING | N |  |  |  |  | Pipe-separated exception types affecting this row |
| `top_loss_reason_code` | STRING | N |  |  |  | downtime_reason.reason_code |  |
| `source_event_count` | INTEGER | Y |  |  |  |  |  |
| `source_count_record_count` | INTEGER | Y |  |  |  |  |  |
| `source_inspection_count` | INTEGER | Y |  |  |  |  |  |
| `calc_version` | STRING | Y |  |  |  |  |  |

### `oee_exception` - Exception / decision log

Every rule that fired during the calculation, with the record it fired on and how it was treated.

- Grain: one row per detected exception
- Primary key: `exception_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `exception_id` | STRING | Y | `^EXC-2026-\d{6}$` |  | Y |  |  |
| `issue_type` | STRING | Y | OVERLAPPING_STATE, COUNT_DECREASE_NO_CORRECTION, SCRAP_EXCEEDS_TOTAL, WRONG_IDEAL_CYCLE_TIME, DOWNTIME_OVERLAPS_BREAK, TIME_GAP, UNANNOTATED_DOWNTIME, LOT_QTY_MISMATCH, MISSING_DISPOSITION, PERFORMANCE_ABOVE_100 |  |  |  |  |
| `severity` | STRING | Y | INFO, WARNING, ERROR |  |  |  |  |
| `record_table` | STRING | Y |  |  |  |  |  |
| `record_id` | STRING | Y |  |  |  |  |  |
| `related_record_ids` | STRING | N |  |  |  |  |  |
| `machine_id` | STRING | N |  |  |  | machine.machine_id |  |
| `shift_id` | STRING | N |  |  |  | shift.shift_id |  |
| `detection_rule` | STRING | Y |  |  |  |  |  |
| `treatment` | STRING | Y |  |  |  |  |  |
| `impact_value` | DECIMAL | N |  |  |  |  |  |
| `impact_unit` | STRING | N |  |  |  |  |  |

## Ground truth (evaluation only, never read by the calculator)

### `ground_truth_anomaly` - Ground truth: injected anomalies

One row per deliberately injected anomaly with the rule that should catch it.

- Grain: one row per anomaly
- Primary key: `gt_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `gt_id` | STRING | Y | `^GT-2026-\d{6}$` |  | Y |  |  |
| `issue_type` | STRING | Y | OVERLAPPING_STATE, COUNT_DECREASE_NO_CORRECTION, SCRAP_EXCEEDS_TOTAL, WRONG_IDEAL_CYCLE_TIME, DOWNTIME_OVERLAPS_BREAK |  |  |  |  |
| `record_table` | STRING | Y |  |  |  |  |  |
| `record_id` | STRING | Y |  |  |  |  |  |
| `machine_id` | STRING | Y |  |  |  |  |  |
| `shift_id` | STRING | N |  |  |  |  |  |
| `injection` | STRING | Y |  |  |  |  | What was changed |
| `original_value` | STRING | N |  |  |  |  |  |
| `injected_value` | STRING | N |  |  |  |  |  |
| `expected_detection` | STRING | Y |  |  |  |  |  |
| `expected_treatment` | STRING | Y |  |  |  |  |  |

### `ground_truth_oee` - Ground truth: expected machine-shift OEE

OEE components computed by the generator from its own simulation (before data-quality anomalies), via a separate code path from the calculator.

- Grain: one row per machine and shift
- Primary key: `machine_shift_key`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `machine_shift_key` | STRING | Y |  |  | Y |  |  |
| `machine_id` | STRING | Y |  |  |  |  |  |
| `shift_id` | STRING | Y |  |  |  |  |  |
| `planned_production_time_s` | INTEGER | Y |  |  |  |  |  |
| `run_time_s` | INTEGER | Y |  |  |  |  |  |
| `total_count` | INTEGER | Y |  |  |  |  |  |
| `good_count` | INTEGER | Y |  |  |  |  |  |
| `ideal_run_time_s` | DECIMAL | Y |  |  |  |  |  |
| `availability` | DECIMAL | N |  |  |  |  |  |
| `performance` | DECIMAL | N |  |  |  |  |  |
| `quality` | DECIMAL | N |  |  |  |  |  |
| `oee` | DECIMAL | N |  |  |  |  |  |

### `ground_truth_downtime_reason` - Ground truth: true stop reasons

The reason the simulator actually used for each unplanned stop (to score annotations).

- Grain: one row per stop event
- Primary key: `event_id`

| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |
|---|---|---|---|---|---|---|---|
| `event_id` | STRING | Y |  |  | Y |  |  |
| `true_reason_code` | STRING | Y |  |  |  |  |  |

## Relationships and cardinality

| Parent | Child | FK column | Cardinality | Optional | Note |
|---|---|---|---|---|---|
| plant | line | `plant_id` | 1:N | no |  |
| plant | shift | `plant_id` | 1:N | no | shift calendar is per plant |
| line | machine | `line_id` | 1:N | no |  |
| machine | machine_product_standard | `machine_id` | 1:N | no | Machine N:M Product via this bridge |
| product | machine_product_standard | `product_id` | 1:N | no | Machine N:M Product via this bridge |
| shift | shift_break | `shift_id` | 1:N (0..2) | yes | unscheduled shifts have no breaks |
| machine | production_order | `machine_id` | 1:N | no |  |
| product | production_order | `product_id` | 1:N | no |  |
| machine_product_standard | production_order | `standard_id` | 1:N | no | standard effective at release |
| production_order | production_order_status_event | `order_id` | 1:N (1..5) | no | append-only lifecycle |
| machine | state_event | `machine_id` | 1:N | no |  |
| shift | state_event | `shift_id` | 1:N | no | events are split at shift boundaries |
| production_order | state_event | `order_id` | 1:N | yes | only RUNNING/CHANGEOVER carry an order |
| downtime_reason | state_event | `reason_code` | 1:N | yes | empty for RUNNING |
| state_event | downtime_annotation | `event_id` | 1:N (0..2) | yes | re-annotation supersedes |
| downtime_annotation | downtime_annotation | `supersedes_annotation_id` | 1:0..1 | yes | self reference |
| production_order | production_count | `order_id` | 1:N | no |  |
| shift | production_count | `shift_id` | 1:N | no |  |
| production_count | production_count | `corrects_count_id` | 1:0..N | yes | correction -> original reading |
| production_order | quality_inspection | `order_id` | 1:N | no |  |
| shift | quality_inspection | `shift_id` | 1:N | no |  |
| shift | oee_aggregate | `shift_id` | 1:N | no | machine, line and plant rows per shift |
| machine | oee_aggregate | `machine_id` | 1:N | yes | MACHINE_SHIFT rows only |
