# Validation summary

150/150 checks passed.

Data exceptions detected (expected, labelled anomalies plus informational findings):

- COUNT_DECREASE_NO_CORRECTION: 3
- DOWNTIME_OVERLAPS_BREAK: 3
- OVERLAPPING_STATE: 3
- SCRAP_EXCEEDS_TOTAL: 3
- UNANNOTATED_DOWNTIME: 49
- WRONG_IDEAL_CYCLE_TIME: 3

| Status | Category | Check | Checked | Failures |
|---|---|---|---:|---:|
| PASS | STRUCTURE | plant: data types | 6 | 0 |
| PASS | STRUCTURE | plant: required fields | 6 | 0 |
| PASS | STRUCTURE | plant: allowed values | 6 | 0 |
| PASS | STRUCTURE | plant: ID / code format | 2 | 0 |
| PASS | STRUCTURE | plant: primary key unique | 1 | 0 |
| PASS | STRUCTURE | line: data types | 12 | 0 |
| PASS | STRUCTURE | line: required fields | 12 | 0 |
| PASS | STRUCTURE | line: allowed values | 12 | 0 |
| PASS | STRUCTURE | line: ID / code format | 2 | 0 |
| PASS | STRUCTURE | line: primary key unique | 2 | 0 |
| PASS | STRUCTURE | machine: data types | 48 | 0 |
| PASS | STRUCTURE | machine: required fields | 48 | 0 |
| PASS | STRUCTURE | machine: allowed values | 48 | 0 |
| PASS | STRUCTURE | machine: ID / code format | 6 | 0 |
| PASS | STRUCTURE | machine: primary key unique | 6 | 0 |
| PASS | STRUCTURE | product: data types | 36 | 0 |
| PASS | STRUCTURE | product: required fields | 36 | 0 |
| PASS | STRUCTURE | product: allowed values | 36 | 0 |
| PASS | STRUCTURE | product: ID / code format | 6 | 0 |
| PASS | STRUCTURE | product: primary key unique | 6 | 0 |
| PASS | STRUCTURE | machine_product_standard: data types | 192 | 0 |
| PASS | STRUCTURE | machine_product_standard: required fields | 192 | 0 |
| PASS | STRUCTURE | machine_product_standard: allowed values | 192 | 0 |
| PASS | STRUCTURE | machine_product_standard: ID / code format | 24 | 0 |
| PASS | STRUCTURE | machine_product_standard: primary key unique | 24 | 0 |
| PASS | STRUCTURE | downtime_reason: data types | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: required fields | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: allowed values | 84 | 0 |
| PASS | STRUCTURE | downtime_reason: ID / code format | 12 | 0 |
| PASS | STRUCTURE | downtime_reason: primary key unique | 12 | 0 |
| PASS | STRUCTURE | shift: data types | 378 | 0 |
| PASS | STRUCTURE | shift: required fields | 378 | 0 |
| PASS | STRUCTURE | shift: allowed values | 378 | 0 |
| PASS | STRUCTURE | shift: ID / code format | 42 | 0 |
| PASS | STRUCTURE | shift: primary key unique | 42 | 0 |
| PASS | STRUCTURE | shift_break: data types | 456 | 0 |
| PASS | STRUCTURE | shift_break: required fields | 456 | 0 |
| PASS | STRUCTURE | shift_break: allowed values | 456 | 0 |
| PASS | STRUCTURE | shift_break: ID / code format | 76 | 0 |
| PASS | STRUCTURE | shift_break: primary key unique | 76 | 0 |
| PASS | STRUCTURE | production_order: data types | 2171 | 0 |
| PASS | STRUCTURE | production_order: required fields | 2171 | 0 |
| PASS | STRUCTURE | production_order: allowed values | 2171 | 0 |
| PASS | STRUCTURE | production_order: ID / code format | 167 | 0 |
| PASS | STRUCTURE | production_order: primary key unique | 167 | 0 |
| PASS | STRUCTURE | production_order_status_event: data types | 3882 | 0 |
| PASS | STRUCTURE | production_order_status_event: required fields | 3882 | 0 |
| PASS | STRUCTURE | production_order_status_event: allowed values | 3882 | 0 |
| PASS | STRUCTURE | production_order_status_event: ID / code format | 647 | 0 |
| PASS | STRUCTURE | production_order_status_event: primary key unique | 647 | 0 |
| PASS | STRUCTURE | state_event: data types | 31110 | 0 |
| PASS | STRUCTURE | state_event: required fields | 31110 | 0 |
| PASS | STRUCTURE | state_event: allowed values | 31110 | 0 |
| PASS | STRUCTURE | state_event: ID / code format | 3111 | 0 |
| PASS | STRUCTURE | state_event: primary key unique | 3111 | 0 |
| PASS | STRUCTURE | downtime_annotation: data types | 3426 | 0 |
| PASS | STRUCTURE | downtime_annotation: required fields | 3426 | 0 |
| PASS | STRUCTURE | downtime_annotation: allowed values | 3426 | 0 |
| PASS | STRUCTURE | downtime_annotation: ID / code format | 571 | 0 |
| PASS | STRUCTURE | downtime_annotation: primary key unique | 571 | 0 |
| PASS | STRUCTURE | production_count: data types | 151503 | 0 |
| PASS | STRUCTURE | production_count: required fields | 151503 | 0 |
| PASS | STRUCTURE | production_count: allowed values | 151503 | 0 |
| PASS | STRUCTURE | production_count: ID / code format | 13773 | 0 |
| PASS | STRUCTURE | production_count: primary key unique | 13773 | 0 |
| PASS | STRUCTURE | quality_inspection: data types | 23179 | 0 |
| PASS | STRUCTURE | quality_inspection: required fields | 23179 | 0 |
| PASS | STRUCTURE | quality_inspection: allowed values | 23179 | 0 |
| PASS | STRUCTURE | quality_inspection: ID / code format | 1783 | 0 |
| PASS | STRUCTURE | quality_inspection: primary key unique | 1783 | 0 |
| PASS | STRUCTURE | oee_aggregate: data types | 12096 | 0 |
| PASS | STRUCTURE | oee_aggregate: required fields | 12096 | 0 |
| PASS | STRUCTURE | oee_aggregate: allowed values | 12096 | 0 |
| PASS | STRUCTURE | oee_aggregate: ID / code format | 378 | 0 |
| PASS | STRUCTURE | oee_aggregate: primary key unique | 378 | 0 |
| PASS | STRUCTURE | oee_exception: data types | 768 | 0 |
| PASS | STRUCTURE | oee_exception: required fields | 768 | 0 |
| PASS | STRUCTURE | oee_exception: allowed values | 768 | 0 |
| PASS | STRUCTURE | oee_exception: ID / code format | 64 | 0 |
| PASS | STRUCTURE | oee_exception: primary key unique | 64 | 0 |
| PASS | FOREIGN_KEY | line.plant_id -> plant.plant_id | 2 | 0 |
| PASS | FOREIGN_KEY | machine.line_id -> line.line_id | 6 | 0 |
| PASS | FOREIGN_KEY | machine_product_standard.machine_id -> machine.machine_id | 24 | 0 |
| PASS | FOREIGN_KEY | machine_product_standard.product_id -> product.product_id | 24 | 0 |
| PASS | FOREIGN_KEY | shift.plant_id -> plant.plant_id | 42 | 0 |
| PASS | FOREIGN_KEY | shift_break.shift_id -> shift.shift_id | 76 | 0 |
| PASS | FOREIGN_KEY | production_order.product_id -> product.product_id | 167 | 0 |
| PASS | FOREIGN_KEY | production_order.machine_id -> machine.machine_id | 167 | 0 |
| PASS | FOREIGN_KEY | production_order.standard_id -> machine_product_standard.standard_id | 167 | 0 |
| PASS | FOREIGN_KEY | production_order_status_event.order_id -> production_order.order_id | 647 | 0 |
| PASS | FOREIGN_KEY | state_event.machine_id -> machine.machine_id | 3111 | 0 |
| PASS | FOREIGN_KEY | state_event.shift_id -> shift.shift_id | 3111 | 0 |
| PASS | FOREIGN_KEY | state_event.reason_code -> downtime_reason.reason_code | 3111 | 0 |
| PASS | FOREIGN_KEY | state_event.order_id -> production_order.order_id | 3111 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.event_id -> state_event.event_id | 571 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.reason_code -> downtime_reason.reason_code | 571 | 0 |
| PASS | FOREIGN_KEY | downtime_annotation.supersedes_annotation_id -> downtime_annotation.annotation_id | 571 | 0 |
| PASS | FOREIGN_KEY | production_count.order_id -> production_order.order_id | 13773 | 0 |
| PASS | FOREIGN_KEY | production_count.machine_id -> machine.machine_id | 13773 | 0 |
| PASS | FOREIGN_KEY | production_count.shift_id -> shift.shift_id | 13773 | 0 |
| PASS | FOREIGN_KEY | production_count.corrects_count_id -> production_count.count_id | 13773 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.order_id -> production_order.order_id | 1783 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.machine_id -> machine.machine_id | 1783 | 0 |
| PASS | FOREIGN_KEY | quality_inspection.shift_id -> shift.shift_id | 1783 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.plant_id -> plant.plant_id | 378 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.line_id -> line.line_id | 378 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.machine_id -> machine.machine_id | 378 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.shift_id -> shift.shift_id | 378 | 0 |
| PASS | FOREIGN_KEY | oee_aggregate.top_loss_reason_code -> downtime_reason.reason_code | 378 | 0 |
| PASS | FOREIGN_KEY | oee_exception.machine_id -> machine.machine_id | 64 | 0 |
| PASS | FOREIGN_KEY | oee_exception.shift_id -> shift.shift_id | 64 | 0 |
| PASS | TEMPORAL | shift: end > start and duration = end - start | 42 | 0 |
| PASS | TEMPORAL | shift calendar contiguous, no overlap | 42 | 0 |
| PASS | TEMPORAL | shift_break inside its shift | 76 | 0 |
| PASS | TEMPORAL | state_event: end > start | 3111 | 0 |
| PASS | RECONCILIATION | state_event: duration = end - start | 3111 | 0 |
| PASS | TEMPORAL | state_event inside its shift | 3111 | 0 |
| PASS | STRUCTURE | state_event: reason/order presence by state | 3111 | 0 |
| PASS | STRUCTURE | state_event IDs ordered by start time per machine | 6 | 0 |
| PASS | TEMPORAL | standard: effective_to > effective_from | 24 | 0 |
| PASS | TEMPORAL | standard versions do not overlap | 18 | 0 |
| PASS | RECONCILIATION | standard: product family matches machine's line | 24 | 0 |
| PASS | FOREIGN_KEY | order: standard matches machine+product | 167 | 0 |
| PASS | TEMPORAL | order: standard effective at release | 167 | 0 |
| PASS | TEMPORAL | order: created <= released <= started <= ended; planned_end > planned_start | 167 | 0 |
| PASS | LIFECYCLE | order lifecycle transitions valid and time-ordered | 167 | 0 |
| PASS | LIFECYCLE | order current_status = latest status event | 167 | 0 |
| PASS | LIFECYCLE | every order has lifecycle history | 167 | 0 |
| PASS | LIFECYCLE | annotation: on a STOPPED event, after it ends, supersedes same event | 571 | 0 |
| PASS | FOREIGN_KEY | count: machine = order's machine | 13773 | 0 |
| PASS | LIFECYCLE | count: correction points at an earlier reading of the same order and shift | 13773 | 0 |
| PASS | TEMPORAL | count: reading timestamp inside its shift | 13773 | 0 |
| PASS | RECONCILIATION | inspection: defects_found <= sample_size | 1783 | 0 |
| PASS | FOREIGN_KEY | inspection: machine = order's machine | 1783 | 0 |
| PASS | DUPLICATES | duplicate state events (machine, start, end, state) | 3111 | 0 |
| PASS | DUPLICATES | duplicate PLC readings (order, ts, counter) | 13711 | 0 |
| PASS | DUPLICATES | duplicate lot dispositions (order, shift) | 369 | 0 |
| PASS | DUPLICATES | duplicate annotations (event, ts, reason) | 571 | 0 |
| PASS | RECONCILIATION | aggregate: planned + unplanned + minor + running + gap = shift length | 378 | 0 |
| PASS | RECONCILIATION | aggregate: PPT = shift length - planned stops | 378 | 0 |
| PASS | RECONCILIATION | aggregate: run time = running + minor = PPT - unplanned - gap | 378 | 0 |
| PASS | RECONCILIATION | aggregate: good = total - scrap - rework | 378 | 0 |
| PASS | RECONCILIATION | aggregate: A, P, Q, OEE recomputed from stored components | 1512 | 0 |
| PASS | RECONCILIATION | aggregate: availability and quality within [0, 1] | 756 | 0 |
| PASS | RECONCILIATION | roll-ups equal the sum of their machine-shift components | 126 | 0 |
| PASS | RECONCILIATION | one machine-shift aggregate per machine x shift | 252 | 0 |
| PASS | RECONCILIATION | count: increment_qty = counter - previous valid reading | 13711 | 0 |
| PASS | RECONCILIATION | aggregate total_count = valid increments + corrections | 252 | 0 |
| PASS | RECONCILIATION | order final status derived from counted quantity | 167 | 0 |
| PASS | RECONCILIATION | unscheduled shifts: PPT = 0, OEE empty, status NOT_SCHEDULED | 252 | 0 |
