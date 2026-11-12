# Validation summary

150/150 checks passed.

Data exceptions detected (expected, labelled anomalies plus informational findings):

- COUNT_DECREASE_NO_CORRECTION: 25
- DOWNTIME_OVERLAPS_BREAK: 25
- OVERLAPPING_STATE: 25
- SCRAP_EXCEEDS_TOTAL: 25
- UNANNOTATED_DOWNTIME: 1110
- WRONG_IDEAL_CYCLE_TIME: 25

| Status | Category | Check | Checked | Failures |
|---|---|---|---:|---:|
| PASS | STRUCTURE | plant: data types | 6 | 0 |
| PASS | STRUCTURE | plant: required fields | 6 | 0 |
| PASS | STRUCTURE | plant: allowed values | 6 | 0 |
| PASS | STRUCTURE | plant: ID / code format | 2 | 0 |
| PASS | STRUCTURE | plant: primary key unique | 1 | 0 |
| PASS | STRUCTURE | line: data types | 30 | 0 |
| PASS | STRUCTURE | line: required fields | 30 | 0 |
| PASS | STRUCTURE | line: allowed values | 30 | 0 |
| PASS | STRUCTURE | line: ID / code format | 5 | 0 |
| PASS | STRUCTURE | line: primary key unique | 5 | 0 |
| PASS | STRUCTURE | machine: data types | 240 | 0 |
| PASS | STRUCTURE | machine: required fields | 240 | 0 |
| PASS | STRUCTURE | machine: allowed values | 240 | 0 |
| PASS | STRUCTURE | machine: ID / code format | 30 | 0 |
| PASS | STRUCTURE | machine: primary key unique | 30 | 0 |
| PASS | STRUCTURE | product: data types | 120 | 0 |
| PASS | STRUCTURE | product: required fields | 120 | 0 |
| PASS | STRUCTURE | product: allowed values | 120 | 0 |
| PASS | STRUCTURE | product: ID / code format | 20 | 0 |
| PASS | STRUCTURE | product: primary key unique | 20 | 0 |
| PASS | STRUCTURE | machine_product_standard: data types | 1256 | 0 |
| PASS | STRUCTURE | machine_product_standard: required fields | 1256 | 0 |
| PASS | STRUCTURE | machine_product_standard: allowed values | 1256 | 0 |
| PASS | STRUCTURE | machine_product_standard: ID / code format | 157 | 0 |
| PASS | STRUCTURE | machine_product_standard: primary key unique | 157 | 0 |
| PASS | STRUCTURE | downtime_reason: data types | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: required fields | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: allowed values | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: ID / code format | 12 | 0 |
| PASS | STRUCTURE | downtime_reason: primary key unique | 12 | 0 |
| PASS | STRUCTURE | shift: data types | 2430 | 0 |
| PASS | STRUCTURE | shift: required fields | 2430 | 0 |
| PASS | STRUCTURE | shift: allowed values | 2430 | 0 |
| PASS | STRUCTURE | shift: ID / code format | 270 | 0 |
| PASS | STRUCTURE | shift: primary key unique | 270 | 0 |
| PASS | STRUCTURE | shift_break: data types | 2892 | 0 |
| PASS | STRUCTURE | shift_break: required fields | 2892 | 0 |
| PASS | STRUCTURE | shift_break: allowed values | 2892 | 0 |
| PASS | STRUCTURE | shift_break: ID / code format | 482 | 0 |
| PASS | STRUCTURE | shift_break: primary key unique | 482 | 0 |
| PASS | STRUCTURE | production_order: data types | 64064 | 0 |
| PASS | STRUCTURE | production_order: required fields | 64064 | 0 |
| PASS | STRUCTURE | production_order: allowed values | 64064 | 0 |
| PASS | STRUCTURE | production_order: ID / code format | 4928 | 0 |
| PASS | STRUCTURE | production_order: primary key unique | 4928 | 0 |
| PASS | STRUCTURE | production_order_status_event: data types | 116010 | 0 |
| PASS | STRUCTURE | production_order_status_event: required fields | 116010 | 0 |
| PASS | STRUCTURE | production_order_status_event: allowed values | 116010 | 0 |
| PASS | STRUCTURE | production_order_status_event: ID / code format | 19335 | 0 |
| PASS | STRUCTURE | production_order_status_event: primary key unique | 19335 | 0 |
| PASS | STRUCTURE | state_event: data types | 1000000 | 0 |
| PASS | STRUCTURE | state_event: required fields | 1000000 | 0 |
| PASS | STRUCTURE | state_event: allowed values | 1000000 | 0 |
| PASS | STRUCTURE | state_event: ID / code format | 100000 | 0 |
| PASS | STRUCTURE | state_event: primary key unique | 100000 | 0 |
| PASS | STRUCTURE | downtime_annotation: data types | 93258 | 0 |
| PASS | STRUCTURE | downtime_annotation: required fields | 93258 | 0 |
| PASS | STRUCTURE | downtime_annotation: allowed values | 93258 | 0 |
| PASS | STRUCTURE | downtime_annotation: ID / code format | 15543 | 0 |
| PASS | STRUCTURE | downtime_annotation: primary key unique | 15543 | 0 |
| PASS | STRUCTURE | production_count: data types | 4872659 | 0 |
| PASS | STRUCTURE | production_count: required fields | 4872659 | 0 |
| PASS | STRUCTURE | production_count: allowed values | 4872659 | 0 |
| PASS | STRUCTURE | production_count: ID / code format | 442969 | 0 |
| PASS | STRUCTURE | production_count: primary key unique | 442969 | 0 |
| PASS | STRUCTURE | quality_inspection: data types | 741403 | 0 |
| PASS | STRUCTURE | quality_inspection: required fields | 741403 | 0 |
| PASS | STRUCTURE | quality_inspection: allowed values | 741403 | 0 |
| PASS | STRUCTURE | quality_inspection: ID / code format | 57031 | 0 |
| PASS | STRUCTURE | quality_inspection: primary key unique | 57031 | 0 |
| PASS | STRUCTURE | oee_aggregate: data types | 311040 | 0 |
| PASS | STRUCTURE | oee_aggregate: required fields | 311040 | 0 |
| PASS | STRUCTURE | oee_aggregate: allowed values | 311040 | 0 |
| PASS | STRUCTURE | oee_aggregate: ID / code format | 9720 | 0 |
| PASS | STRUCTURE | oee_aggregate: primary key unique | 9720 | 0 |
| PASS | STRUCTURE | oee_exception: data types | 14820 | 0 |
| PASS | STRUCTURE | oee_exception: required fields | 14820 | 0 |
| PASS | STRUCTURE | oee_exception: allowed values | 14820 | 0 |
| PASS | STRUCTURE | oee_exception: ID / code format | 1235 | 0 |
| PASS | STRUCTURE | oee_exception: primary key unique | 1235 | 0 |
| PASS | FOREIGN_KEY | line.plant_id -> plant.plant_id | 5 | 0 |
| PASS | FOREIGN_KEY | machine.line_id -> line.line_id | 30 | 0 |
| PASS | FOREIGN_KEY | machine_product_standard.machine_id -> machine.machine_id | 157 | 0 |
| PASS | FOREIGN_KEY | machine_product_standard.product_id -> product.product_id | 157 | 0 |
| PASS | FOREIGN_KEY | shift.plant_id -> plant.plant_id | 270 | 0 |
| PASS | FOREIGN_KEY | shift_break.shift_id -> shift.shift_id | 482 | 0 |
| PASS | FOREIGN_KEY | production_order.product_id -> product.product_id | 4928 | 0 |
| PASS | FOREIGN_KEY | production_order.machine_id -> machine.machine_id | 4928 | 0 |
| PASS | FOREIGN_KEY | production_order.standard_id -> machine_product_standard.standard_id | 4928 | 0 |
| PASS | FOREIGN_KEY | production_order_status_event.order_id -> production_order.order_id | 19335 | 0 |
| PASS | FOREIGN_KEY | state_event.machine_id -> machine.machine_id | 100000 | 0 |
| PASS | FOREIGN_KEY | state_event.shift_id -> shift.shift_id | 100000 | 0 |
| PASS | FOREIGN_KEY | state_event.reason_code -> downtime_reason.reason_code | 100000 | 0 |
| PASS | FOREIGN_KEY | state_event.order_id -> production_order.order_id | 100000 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.event_id -> state_event.event_id | 15543 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.reason_code -> downtime_reason.reason_code | 15543 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.supersedes_annotation_id -> downtime_annotation.annotation_id | 15543 | 0 |
| PASS | FOREIGN_KEY | production_count.order_id -> production_order.order_id | 442969 | 0 |
| PASS | FOREIGN_KEY | production_count.machine_id -> machine.machine_id | 442969 | 0 |
| PASS | FOREIGN_KEY | production_count.shift_id -> shift.shift_id | 442969 | 0 |
| PASS | FOREIGN_KEY | production_count.corrects_count_id -> production_count.count_id | 442969 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.order_id -> production_order.order_id | 57031 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.machine_id -> machine.machine_id | 57031 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.shift_id -> shift.shift_id | 57031 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.plant_id -> plant.plant_id | 9720 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.line_id -> line.line_id | 9720 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.machine_id -> machine.machine_id | 9720 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.shift_id -> shift.shift_id | 9720 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.top_loss_reason_code -> downtime_reason.reason_code | 9720 | 0 |
| PASS | FOREIGN_KEY | oee_exception.machine_id -> machine.machine_id | 1235 | 0 |
| PASS | FOREIGN_KEY | oee_exception.shift_id -> shift.shift_id | 1235 | 0 |
| PASS | TEMPORAL | shift: end > start and duration = end - start | 270 | 0 |
| PASS | TEMPORAL | shift calendar contiguous, no overlap | 270 | 0 |
| PASS | TEMPORAL | shift_break inside its shift | 482 | 0 |
| PASS | TEMPORAL | state_event: end > start | 100000 | 0 |
| PASS | RECONCILIATION | state_event: duration = end - start | 100000 | 0 |
| PASS | TEMPORAL | state_event inside its shift | 100000 | 0 |
| PASS | STRUCTURE | state_event: reason/order presence by state | 100000 | 0 |
| PASS | STRUCTURE | state_event IDs ordered by start time per machine | 30 | 0 |
| PASS | TEMPORAL | standard: effective_to > effective_from | 157 | 0 |
| PASS | TEMPORAL | standard versions do not overlap | 120 | 0 |
| PASS | RECONCILIATION | standard: product family matches machine's line | 157 | 0 |
| PASS | FOREIGN_KEY | order: standard matches machine+product | 4928 | 0 |
| PASS | TEMPORAL | order: standard effective at release | 4928 | 0 |
| PASS | TEMPORAL | order: created <= released <= started <= ended; planned_end > planned_start | 4928 | 0 |
| PASS | LIFECYCLE | order lifecycle transitions valid and time-ordered | 4928 | 0 |
| PASS | LIFECYCLE | order current_status = latest status event | 4928 | 0 |
| PASS | LIFECYCLE | every order has lifecycle history | 4928 | 0 |
| PASS | LIFECYCLE | annotation: on a STOPPED event, after it ends, supersedes same event | 15543 | 0 |
| PASS | FOREIGN_KEY | count: machine = order's machine | 442969 | 0 |
| PASS | LIFECYCLE | count: correction points at an earlier reading of the same order and shift | 442969 | 0 |
| PASS | TEMPORAL | count: reading timestamp inside its shift | 442969 | 0 |
| PASS | RECONCILIATION | inspection: defects_found <= sample_size | 57031 | 0 |
| PASS | FOREIGN_KEY | inspection: machine = order's machine | 57031 | 0 |
| PASS | DUPLICATES | duplicate state events (machine, start, end, state) | 100000 | 0 |
| PASS | DUPLICATES | duplicate PLC readings (order, ts, counter) | 440969 | 0 |
| PASS | DUPLICATES | duplicate lot dispositions (order, shift) | 11573 | 0 |
| PASS | DUPLICATES | duplicate annotations (event, ts, reason) | 15543 | 0 |
| PASS | RECONCILIATION | aggregate: planned + unplanned + minor + running + gap = shift length | 9720 | 0 |
| PASS | RECONCILIATION | aggregate: PPT = shift length - planned stops | 9720 | 0 |
| PASS | RECONCILIATION | aggregate: run time = running + minor = PPT - unplanned - gap | 9720 | 0 |
| PASS | RECONCILIATION | aggregate: good = total - scrap - rework | 9720 | 0 |
| PASS | RECONCILIATION | aggregate: A, P, Q, OEE recomputed from stored components | 38880 | 0 |
| PASS | RECONCILIATION | aggregate: availability and quality within [0, 1] | 19440 | 0 |
| PASS | RECONCILIATION | roll-ups equal the sum of their machine-shift components | 1620 | 0 |
| PASS | RECONCILIATION | one machine-shift aggregate per machine x shift | 8100 | 0 |
| PASS | RECONCILIATION | count: increment_qty = counter - previous valid reading | 440969 | 0 |
| PASS | RECONCILIATION | aggregate total_count = valid increments + corrections | 8100 | 0 |
| PASS | RECONCILIATION | order final status derived from counted quantity | 4928 | 0 |
| PASS | RECONCILIATION | unscheduled shifts: PPT = 0, OEE empty, status NOT_SCHEDULED | 8100 | 0 |
