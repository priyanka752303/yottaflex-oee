-- Generated from oee/schema.py. Timestamps are ISO-8601 with UTC offset; booleans are 0/1.
PRAGMA foreign_keys = ON;

-- Plant: Manufacturing site. Owns the shift calendar.
CREATE TABLE plant (
  plant_id TEXT PRIMARY KEY,
  plant_name TEXT NOT NULL,
  timezone TEXT NOT NULL CHECK (timezone IN ('Asia/Kolkata')),
  country_code TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
  effective_from TEXT NOT NULL
);

-- Line: Production line inside a plant; one product family per line.
CREATE TABLE line (
  line_id TEXT PRIMARY KEY,
  plant_id TEXT NOT NULL,
  line_name TEXT NOT NULL,
  product_family TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'INACTIVE')),
  effective_from TEXT NOT NULL,
  FOREIGN KEY (plant_id) REFERENCES plant(plant_id) DEFERRABLE INITIALLY DEFERRED
);

-- Machine: Asset that emits state events and part counts.
CREATE TABLE machine (
  machine_id TEXT PRIMARY KEY,
  line_id TEXT NOT NULL,
  machine_name TEXT NOT NULL,
  machine_type TEXT NOT NULL CHECK (machine_type IN ('CNC_MILL', 'CNC_LATHE', 'INJECTION_MOLDER', 'STAMPING_PRESS', 'GRINDER')),
  position_in_line INTEGER NOT NULL,
  commissioned_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED')),
  effective_from TEXT NOT NULL,
  FOREIGN KEY (line_id) REFERENCES line(line_id) DEFERRABLE INITIALLY DEFERRED
);

-- Product: Part number that can be produced.
CREATE TABLE product (
  product_id TEXT PRIMARY KEY,
  product_name TEXT NOT NULL,
  product_family TEXT NOT NULL,
  unit_of_measure TEXT NOT NULL CHECK (unit_of_measure IN ('EA')),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'OBSOLETE')),
  effective_from TEXT NOT NULL
);

-- Ideal cycle time (Machine x Product bridge): Bridge table resolving Machine N:M Product. Holds the versioned ideal cycle time used for Performance.
CREATE TABLE machine_product_standard (
  standard_id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  ideal_cycle_time_s REAL NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  approved_by_role TEXT NOT NULL CHECK (approved_by_role IN ('PLANT_OPERATOR', 'MAINTENANCE_ENGINEER', 'QUALITY_ENGINEER', 'PRODUCTION_PLANNER', 'OT_IT_ADMINISTRATOR')),
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (product_id) REFERENCES product(product_id) DEFERRABLE INITIALLY DEFERRED
);

-- DowntimeReason: Reason code catalogue and its OEE treatment.
CREATE TABLE downtime_reason (
  reason_code TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('PLANNED_STOP', 'UNPLANNED_STOP', 'SETUP', 'MINOR_STOP', 'UNKNOWN')),
  oee_loss_bucket TEXT NOT NULL CHECK (oee_loss_bucket IN ('NONE', 'AVAILABILITY', 'PERFORMANCE')),
  is_planned INTEGER NOT NULL,
  requires_annotation INTEGER NOT NULL,
  effective_from TEXT NOT NULL
);

-- Shift: Plant shift calendar instance (date + shift code).
CREATE TABLE shift (
  shift_id TEXT PRIMARY KEY,
  plant_id TEXT NOT NULL,
  shift_date TEXT NOT NULL,
  shift_code TEXT NOT NULL CHECK (shift_code IN ('A', 'B', 'C')),
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_s INTEGER NOT NULL,
  is_production_scheduled INTEGER NOT NULL,
  calendar_note TEXT CHECK (calendar_note IN ('WEEKEND_NIGHT', 'HOLIDAY')),
  FOREIGN KEY (plant_id) REFERENCES plant(plant_id) DEFERRABLE INITIALLY DEFERRED
);

-- Planned break (child of Shift): Planned break window. Always planned downtime, whatever the machine reports.
CREATE TABLE shift_break (
  break_id TEXT PRIMARY KEY,
  shift_id TEXT NOT NULL,
  break_type TEXT NOT NULL CHECK (break_type IN ('TEA', 'MEAL')),
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_s INTEGER NOT NULL,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED
);

-- ProductionOrder: Work order to make a product on one machine.
CREATE TABLE production_order (
  order_id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  standard_id TEXT NOT NULL,
  ideal_cycle_time_s REAL NOT NULL,
  planned_qty INTEGER NOT NULL,
  planned_start_ts TEXT NOT NULL,
  planned_end_ts TEXT NOT NULL,
  created_ts TEXT NOT NULL,
  released_ts TEXT,
  actual_start_ts TEXT,
  actual_end_ts TEXT,
  current_status TEXT NOT NULL CHECK (current_status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED_SHORT', 'CANCELLED')),
  FOREIGN KEY (product_id) REFERENCES product(product_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (standard_id) REFERENCES machine_product_standard(standard_id) DEFERRABLE INITIALLY DEFERRED
);

-- ProductionOrder lifecycle history: Append-only history of order status changes (history is never overwritten).
CREATE TABLE production_order_status_event (
  status_event_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  from_status TEXT CHECK (from_status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED_SHORT', 'CANCELLED')),
  to_status TEXT NOT NULL CHECK (to_status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED_SHORT', 'CANCELLED')),
  changed_ts TEXT NOT NULL,
  changed_by_role TEXT NOT NULL CHECK (changed_by_role IN ('PLANT_OPERATOR', 'MAINTENANCE_ENGINEER', 'QUALITY_ENGINEER', 'PRODUCTION_PLANNER', 'OT_IT_ADMINISTRATOR')),
  FOREIGN KEY (order_id) REFERENCES production_order(order_id) DEFERRABLE INITIALLY DEFERRED
);

-- StateEvent: Machine state interval from PLC/MES. Split at shift boundaries. Never updated after insert.
CREATE TABLE state_event (
  event_id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  shift_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('RUNNING', 'STOPPED', 'CHANGEOVER', 'PLANNED_STOP')),
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_s INTEGER NOT NULL,
  reason_code TEXT,
  order_id TEXT,
  source TEXT NOT NULL CHECK (source IN ('PLC', 'MES')),
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (reason_code) REFERENCES downtime_reason(reason_code) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (order_id) REFERENCES production_order(order_id) DEFERRABLE INITIALLY DEFERRED
);

-- Downtime reason annotation: Append-only reason assignment for a stop. A later annotation supersedes an earlier one.
CREATE TABLE downtime_annotation (
  annotation_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  annotated_by_role TEXT NOT NULL CHECK (annotated_by_role IN ('PLANT_OPERATOR', 'MAINTENANCE_ENGINEER', 'QUALITY_ENGINEER', 'PRODUCTION_PLANNER', 'OT_IT_ADMINISTRATOR')),
  annotated_ts TEXT NOT NULL,
  supersedes_annotation_id TEXT,
  FOREIGN KEY (event_id) REFERENCES state_event(event_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (reason_code) REFERENCES downtime_reason(reason_code) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (supersedes_annotation_id) REFERENCES downtime_annotation(annotation_id) DEFERRABLE INITIALLY DEFERRED
);

-- ProductionCount: PLC counter readings (cumulative per order) plus manual corrections. Originals are never edited.
CREATE TABLE production_count (
  count_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  shift_id TEXT NOT NULL,
  record_ts TEXT NOT NULL,
  record_type TEXT NOT NULL CHECK (record_type IN ('PLC_READING', 'MANUAL_CORRECTION')),
  counter_value INTEGER,
  increment_qty INTEGER NOT NULL,
  corrects_count_id TEXT,
  correction_reason TEXT CHECK (correction_reason IN ('SENSOR_DOUBLE_COUNT', 'COUNTER_RESET')),
  entered_by_role TEXT NOT NULL CHECK (entered_by_role IN ('PLANT_OPERATOR', 'MAINTENANCE_ENGINEER', 'QUALITY_ENGINEER', 'PRODUCTION_PLANNER', 'OT_IT_ADMINISTRATOR')),
  FOREIGN KEY (order_id) REFERENCES production_order(order_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (corrects_count_id) REFERENCES production_count(count_id) DEFERRABLE INITIALLY DEFERRED
);

-- QualityInspection: SAMPLE = periodic in-process check (informational). LOT_DISPOSITION = scrap/rework decision for the units of one order made in one shift (feeds Quality).
CREATE TABLE quality_inspection (
  inspection_id TEXT PRIMARY KEY,
  inspection_type TEXT NOT NULL CHECK (inspection_type IN ('SAMPLE', 'LOT_DISPOSITION')),
  order_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  shift_id TEXT NOT NULL,
  inspection_ts TEXT NOT NULL,
  sample_size INTEGER,
  defects_found INTEGER,
  inspected_qty INTEGER,
  scrap_qty INTEGER,
  rework_qty INTEGER,
  result TEXT NOT NULL CHECK (result IN ('PASS', 'FAIL', 'DISPOSITIONED')),
  inspector_role TEXT NOT NULL CHECK (inspector_role IN ('PLANT_OPERATOR', 'MAINTENANCE_ENGINEER', 'QUALITY_ENGINEER', 'PRODUCTION_PLANNER', 'OT_IT_ADMINISTRATOR')),
  FOREIGN KEY (order_id) REFERENCES production_order(order_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED
);

-- OEEAggregate: OEE and its time/count components, computed only from input tables. Line and plant rows are time/count-weighted roll-ups, never averages of ratios.
CREATE TABLE oee_aggregate (
  aggregate_id TEXT PRIMARY KEY,
  aggregate_level TEXT NOT NULL CHECK (aggregate_level IN ('MACHINE_SHIFT', 'LINE_SHIFT', 'PLANT_SHIFT')),
  plant_id TEXT NOT NULL,
  line_id TEXT,
  machine_id TEXT,
  shift_id TEXT NOT NULL,
  shift_duration_s INTEGER NOT NULL,
  planned_stop_s INTEGER NOT NULL,
  planned_production_time_s INTEGER NOT NULL,
  unplanned_stop_s INTEGER NOT NULL,
  minor_stop_s INTEGER NOT NULL,
  gap_s INTEGER NOT NULL,
  overlap_s INTEGER NOT NULL,
  downtime_in_break_s INTEGER NOT NULL,
  running_s INTEGER NOT NULL,
  run_time_s INTEGER NOT NULL,
  total_count INTEGER NOT NULL,
  scrap_count INTEGER NOT NULL,
  rework_count INTEGER NOT NULL,
  good_count INTEGER NOT NULL,
  ideal_run_time_s REAL NOT NULL,
  availability REAL,
  performance REAL,
  quality REAL,
  oee REAL,
  data_quality_status TEXT NOT NULL CHECK (data_quality_status IN ('CLEAN', 'EXCEPTION', 'NOT_SCHEDULED')),
  exception_codes TEXT,
  top_loss_reason_code TEXT,
  source_event_count INTEGER NOT NULL,
  source_count_record_count INTEGER NOT NULL,
  source_inspection_count INTEGER NOT NULL,
  calc_version TEXT NOT NULL,
  FOREIGN KEY (plant_id) REFERENCES plant(plant_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (line_id) REFERENCES line(line_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (top_loss_reason_code) REFERENCES downtime_reason(reason_code) DEFERRABLE INITIALLY DEFERRED
);

-- Exception / decision log: Every rule that fired during the calculation, with the record it fired on and how it was treated.
CREATE TABLE oee_exception (
  exception_id TEXT PRIMARY KEY,
  issue_type TEXT NOT NULL CHECK (issue_type IN ('OVERLAPPING_STATE', 'COUNT_DECREASE_NO_CORRECTION', 'SCRAP_EXCEEDS_TOTAL', 'WRONG_IDEAL_CYCLE_TIME', 'DOWNTIME_OVERLAPS_BREAK', 'TIME_GAP', 'UNANNOTATED_DOWNTIME', 'LOT_QTY_MISMATCH', 'MISSING_DISPOSITION', 'PERFORMANCE_ABOVE_100')),
  severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
  record_table TEXT NOT NULL,
  record_id TEXT NOT NULL,
  related_record_ids TEXT,
  machine_id TEXT,
  shift_id TEXT,
  detection_rule TEXT NOT NULL,
  treatment TEXT NOT NULL,
  impact_value REAL,
  impact_unit TEXT,
  FOREIGN KEY (machine_id) REFERENCES machine(machine_id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (shift_id) REFERENCES shift(shift_id) DEFERRABLE INITIALLY DEFERRED
);

-- Ground truth: injected anomalies: One row per deliberately injected anomaly with the rule that should catch it.
CREATE TABLE ground_truth_anomaly (
  gt_id TEXT PRIMARY KEY,
  issue_type TEXT NOT NULL CHECK (issue_type IN ('OVERLAPPING_STATE', 'COUNT_DECREASE_NO_CORRECTION', 'SCRAP_EXCEEDS_TOTAL', 'WRONG_IDEAL_CYCLE_TIME', 'DOWNTIME_OVERLAPS_BREAK')),
  record_table TEXT NOT NULL,
  record_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  shift_id TEXT,
  injection TEXT NOT NULL,
  original_value TEXT,
  injected_value TEXT,
  expected_detection TEXT NOT NULL,
  expected_treatment TEXT NOT NULL
);

-- Ground truth: expected machine-shift OEE: OEE components computed by the generator from its own simulation (before data-quality anomalies), via a separate code path from the calculator.
CREATE TABLE ground_truth_oee (
  machine_shift_key TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  shift_id TEXT NOT NULL,
  planned_production_time_s INTEGER NOT NULL,
  run_time_s INTEGER NOT NULL,
  total_count INTEGER NOT NULL,
  good_count INTEGER NOT NULL,
  ideal_run_time_s REAL NOT NULL,
  availability REAL,
  performance REAL,
  quality REAL,
  oee REAL
);

-- Ground truth: true stop reasons: The reason the simulator actually used for each unplanned stop (to score annotations).
CREATE TABLE ground_truth_downtime_reason (
  event_id TEXT PRIMARY KEY,
  true_reason_code TEXT NOT NULL
);
