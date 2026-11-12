"""Single source of truth for every table.

The same definitions drive: the data dictionary (docs), the SQL DDL, the JSON typing,
and the structural validation (types, required, enums, patterns, PK, FK).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ids import PATTERNS

STATES = ("RUNNING", "STOPPED", "CHANGEOVER", "PLANNED_STOP")
ORDER_STATUSES = ("PLANNED", "RELEASED", "IN_PROGRESS", "COMPLETED", "CLOSED_SHORT", "CANCELLED")
ORDER_TRANSITIONS = {
    None: {"PLANNED"},
    "PLANNED": {"RELEASED", "CANCELLED"},
    "RELEASED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CLOSED_SHORT"},
    "COMPLETED": set(),
    "CLOSED_SHORT": set(),
    "CANCELLED": set(),
}
ROLES = ("PLANT_OPERATOR", "MAINTENANCE_ENGINEER", "QUALITY_ENGINEER", "PRODUCTION_PLANNER",
         "OT_IT_ADMINISTRATOR")
ISSUE_TYPES = ("OVERLAPPING_STATE", "COUNT_DECREASE_NO_CORRECTION", "SCRAP_EXCEEDS_TOTAL",
               "WRONG_IDEAL_CYCLE_TIME", "DOWNTIME_OVERLAPS_BREAK")
EXCEPTION_TYPES = ISSUE_TYPES + ("TIME_GAP", "UNANNOTATED_DOWNTIME", "LOT_QTY_MISMATCH",
                                 "MISSING_DISPOSITION", "PERFORMANCE_ABOVE_100")


@dataclass(frozen=True)
class F:
    name: str
    type: str  # STRING | INTEGER | DECIMAL | TIMESTAMP | DATE | BOOLEAN
    required: bool = True
    allowed: tuple | None = None
    pattern: str | None = None
    unit: str | None = None
    unique: bool = False
    fk: str | None = None  # "table.column"
    rule: str = ""
    desc: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    entity: str
    layer: str  # input | derived | ground_truth
    description: str
    grain: str
    pk: str
    fields: tuple = field(default_factory=tuple)
    lifecycle: str = ""
    effective_dating: str = ""

    def field(self, name: str) -> F:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    @property
    def columns(self) -> list[str]:
        return [f.name for f in self.fields]


P = PATTERNS
TS = "TIMESTAMP"

TABLES: list[Table] = [
    Table("plant", "Plant", "input", "Manufacturing site. Owns the shift calendar.", "one row per plant", "plant_id", (
        F("plant_id", "STRING", pattern=P["plant"], unique=True, desc="Plant identifier"),
        F("plant_name", "STRING", desc="Display name"),
        F("timezone", "STRING", allowed=("Asia/Kolkata",), desc="IANA time zone of all local timestamps"),
        F("country_code", "STRING", pattern=r"^[A-Z]{2}$", desc="ISO 3166-1 alpha-2"),
        F("status", "STRING", allowed=("ACTIVE", "INACTIVE")),
        F("effective_from", "DATE", desc="Date the plant record became valid"),
    ), lifecycle="ACTIVE -> INACTIVE", effective_dating="effective_from"),
    Table("line", "Line", "input", "Production line inside a plant; one product family per line.",
          "one row per line", "line_id", (
        F("line_id", "STRING", pattern=P["line"], unique=True),
        F("plant_id", "STRING", fk="plant.plant_id"),
        F("line_name", "STRING"),
        F("product_family", "STRING", desc="Family of products the line is qualified for"),
        F("status", "STRING", allowed=("ACTIVE", "INACTIVE")),
        F("effective_from", "DATE"),
    ), lifecycle="ACTIVE -> INACTIVE", effective_dating="effective_from"),
    Table("machine", "Machine", "input", "Asset that emits state events and part counts.",
          "one row per machine", "machine_id", (
        F("machine_id", "STRING", pattern=P["machine"], unique=True),
        F("line_id", "STRING", fk="line.line_id"),
        F("machine_name", "STRING"),
        F("machine_type", "STRING", allowed=("CNC_MILL", "CNC_LATHE", "INJECTION_MOLDER", "STAMPING_PRESS", "GRINDER")),
        F("position_in_line", "INTEGER", rule=">= 1, unique within line"),
        F("commissioned_date", "DATE", rule="<= effective_from of any standard"),
        F("status", "STRING", allowed=("ACTIVE", "MAINTENANCE", "DECOMMISSIONED")),
        F("effective_from", "DATE"),
    ), lifecycle="ACTIVE <-> MAINTENANCE -> DECOMMISSIONED", effective_dating="effective_from"),
    Table("product", "Product", "input", "Part number that can be produced.", "one row per product", "product_id", (
        F("product_id", "STRING", pattern=P["product"], unique=True),
        F("product_name", "STRING"),
        F("product_family", "STRING", rule="matches the family of every line that makes it"),
        F("unit_of_measure", "STRING", allowed=("EA",)),
        F("status", "STRING", allowed=("ACTIVE", "OBSOLETE")),
        F("effective_from", "DATE"),
    ), lifecycle="ACTIVE -> OBSOLETE", effective_dating="effective_from"),
    Table("machine_product_standard", "Ideal cycle time (Machine x Product bridge)", "input",
          "Bridge table resolving Machine N:M Product. Holds the versioned ideal cycle time used for Performance.",
          "one row per machine, product and version", "standard_id", (
        F("standard_id", "STRING", pattern=P["standard"], unique=True),
        F("machine_id", "STRING", fk="machine.machine_id"),
        F("product_id", "STRING", fk="product.product_id"),
        F("version", "INTEGER", rule=">= 1, consecutive per machine+product"),
        F("ideal_cycle_time_s", "DECIMAL", unit="seconds per unit", rule="> 0"),
        F("effective_from", TS, rule="versions of one machine+product do not overlap"),
        F("effective_to", TS, required=False, rule="> effective_from; empty = open-ended"),
        F("approved_by_role", "STRING", allowed=ROLES),
    ), effective_dating="effective_from / effective_to (half-open interval)"),
    Table("downtime_reason", "DowntimeReason", "input", "Reason code catalogue and its OEE treatment.",
          "one row per reason code", "reason_code", (
        F("reason_code", "STRING", pattern=P["reason"], unique=True),
        F("description", "STRING"),
        F("category", "STRING", allowed=("PLANNED_STOP", "UNPLANNED_STOP", "SETUP", "MINOR_STOP", "UNKNOWN")),
        F("oee_loss_bucket", "STRING", allowed=("NONE", "AVAILABILITY", "PERFORMANCE"),
          desc="Where the time lands in OEE. NONE = excluded from planned production time"),
        F("is_planned", "BOOLEAN"),
        F("requires_annotation", "BOOLEAN", desc="Operator must give a reason for this kind of stop"),
        F("effective_from", "DATE"),
    ), effective_dating="effective_from"),
    Table("shift", "Shift", "input", "Plant shift calendar instance (date + shift code).",
          "one row per plant, date and shift code", "shift_id", (
        F("shift_id", "STRING", pattern=P["shift"], unique=True),
        F("plant_id", "STRING", fk="plant.plant_id"),
        F("shift_date", "DATE", rule="date on which the shift starts"),
        F("shift_code", "STRING", allowed=("A", "B", "C")),
        F("start_ts", TS),
        F("end_ts", TS, rule="> start_ts; shifts of a plant are contiguous and do not overlap"),
        F("duration_s", "INTEGER", unit="seconds", rule="= end_ts - start_ts"),
        F("is_production_scheduled", "BOOLEAN", desc="false = plant closed (weekend night / holiday)"),
        F("calendar_note", "STRING", required=False, allowed=("WEEKEND_NIGHT", "HOLIDAY")),
    )),
    Table("shift_break", "Planned break (child of Shift)", "input",
          "Planned break window. Always planned downtime, whatever the machine reports.",
          "one row per break window", "break_id", (
        F("break_id", "STRING", pattern=P["break"], unique=True),
        F("shift_id", "STRING", fk="shift.shift_id"),
        F("break_type", "STRING", allowed=("TEA", "MEAL")),
        F("start_ts", TS, rule=">= shift.start_ts"),
        F("end_ts", TS, rule="<= shift.end_ts and > start_ts"),
        F("duration_s", "INTEGER", unit="seconds", rule="= end_ts - start_ts"),
    )),
    Table("production_order", "ProductionOrder", "input", "Work order to make a product on one machine.",
          "one row per order", "order_id", (
        F("order_id", "STRING", pattern=P["order"], unique=True),
        F("product_id", "STRING", fk="product.product_id"),
        F("machine_id", "STRING", fk="machine.machine_id"),
        F("standard_id", "STRING", fk="machine_product_standard.standard_id",
          rule="same machine+product; effective at released_ts"),
        F("ideal_cycle_time_s", "DECIMAL", unit="seconds per unit",
          rule="snapshot copied from the standard at release; must equal it (+/- 0.05 s)"),
        F("planned_qty", "INTEGER", unit="units", rule="> 0"),
        F("planned_start_ts", TS),
        F("planned_end_ts", TS, rule="> planned_start_ts"),
        F("created_ts", TS, rule="<= released_ts"),
        F("released_ts", TS, required=False),
        F("actual_start_ts", TS, required=False, rule=">= released_ts"),
        F("actual_end_ts", TS, required=False, rule=">= actual_start_ts"),
        F("current_status", "STRING", allowed=ORDER_STATUSES, rule="= to_status of the latest status event"),
    ), lifecycle="PLANNED -> RELEASED -> IN_PROGRESS -> COMPLETED | CLOSED_SHORT; PLANNED/RELEASED -> CANCELLED"),
    Table("production_order_status_event", "ProductionOrder lifecycle history", "input",
          "Append-only history of order status changes (history is never overwritten).",
          "one row per status change", "status_event_id", (
        F("status_event_id", "STRING", pattern=P["order_status_event"], unique=True),
        F("order_id", "STRING", fk="production_order.order_id"),
        F("from_status", "STRING", required=False, allowed=ORDER_STATUSES),
        F("to_status", "STRING", allowed=ORDER_STATUSES, rule="allowed transition from from_status"),
        F("changed_ts", TS, rule="non-decreasing within an order"),
        F("changed_by_role", "STRING", allowed=ROLES),
    )),
    Table("state_event", "StateEvent", "input",
          "Machine state interval from PLC/MES. Split at shift boundaries. Never updated after insert.",
          "one row per machine state interval", "event_id", (
        F("event_id", "STRING", pattern=P["event"], unique=True, rule="EVT-<machine-id>-<seq>, seq ordered by start_ts"),
        F("machine_id", "STRING", fk="machine.machine_id"),
        F("shift_id", "STRING", fk="shift.shift_id", rule="event lies inside the shift window"),
        F("state", "STRING", allowed=STATES),
        F("start_ts", TS),
        F("end_ts", TS, rule="> start_ts"),
        F("duration_s", "INTEGER", unit="seconds", rule="= end_ts - start_ts"),
        F("reason_code", "STRING", required=False, fk="downtime_reason.reason_code",
          rule="empty only for RUNNING; DR-UNASSIGNED until annotated"),
        F("order_id", "STRING", required=False, fk="production_order.order_id",
          rule="required for RUNNING and CHANGEOVER"),
        F("source", "STRING", allowed=("PLC", "MES")),
    )),
    Table("downtime_annotation", "Downtime reason annotation", "input",
          "Append-only reason assignment for a stop. A later annotation supersedes an earlier one.",
          "one row per annotation", "annotation_id", (
        F("annotation_id", "STRING", pattern=P["annotation"], unique=True),
        F("event_id", "STRING", fk="state_event.event_id", rule="event is STOPPED"),
        F("reason_code", "STRING", fk="downtime_reason.reason_code"),
        F("annotated_by_role", "STRING", allowed=ROLES),
        F("annotated_ts", TS, rule=">= event end_ts"),
        F("supersedes_annotation_id", "STRING", required=False, fk="downtime_annotation.annotation_id",
          rule="same event_id; earlier annotated_ts"),
    )),
    Table("production_count", "ProductionCount", "input",
          "PLC counter readings (cumulative per order) plus manual corrections. Originals are never edited.",
          "one row per counter reading or correction", "count_id", (
        F("count_id", "STRING", pattern=P["count"], unique=True, rule="CNT-<order-id>-<seq>, seq ordered by record_ts"),
        F("order_id", "STRING", fk="production_order.order_id"),
        F("machine_id", "STRING", fk="machine.machine_id", rule="= production_order.machine_id"),
        F("shift_id", "STRING", fk="shift.shift_id",
          rule="reading: shift containing record_ts; correction: shift of the corrected reading"),
        F("record_ts", TS),
        F("record_type", "STRING", allowed=("PLC_READING", "MANUAL_CORRECTION")),
        F("counter_value", "INTEGER", required=False, unit="units",
          rule="PLC_READING only; cumulative since order start; must not decrease"),
        F("increment_qty", "INTEGER", unit="units",
          rule="reading: counter_value - previous valid reading; correction: signed adjustment"),
        F("corrects_count_id", "STRING", required=False, fk="production_count.count_id",
          rule="MANUAL_CORRECTION only; points at the original reading"),
        F("correction_reason", "STRING", required=False, allowed=("SENSOR_DOUBLE_COUNT", "COUNTER_RESET")),
        F("entered_by_role", "STRING", allowed=ROLES),
    )),
    Table("quality_inspection", "QualityInspection", "input",
          "SAMPLE = periodic in-process check (informational). LOT_DISPOSITION = scrap/rework decision for the "
          "units of one order made in one shift (feeds Quality).",
          "one row per inspection", "inspection_id", (
        F("inspection_id", "STRING", pattern=P["qc"], unique=True),
        F("inspection_type", "STRING", allowed=("SAMPLE", "LOT_DISPOSITION")),
        F("order_id", "STRING", fk="production_order.order_id"),
        F("machine_id", "STRING", fk="machine.machine_id"),
        F("shift_id", "STRING", fk="shift.shift_id", rule="shift whose output is inspected"),
        F("inspection_ts", TS),
        F("sample_size", "INTEGER", required=False, unit="units", rule="SAMPLE only; > 0"),
        F("defects_found", "INTEGER", required=False, unit="units", rule="SAMPLE only; <= sample_size"),
        F("inspected_qty", "INTEGER", required=False, unit="units", rule="LOT_DISPOSITION only; = counted total"),
        F("scrap_qty", "INTEGER", required=False, unit="units", rule="LOT_DISPOSITION only; scrap+rework <= total"),
        F("rework_qty", "INTEGER", required=False, unit="units", rule="LOT_DISPOSITION only"),
        F("result", "STRING", allowed=("PASS", "FAIL", "DISPOSITIONED")),
        F("inspector_role", "STRING", allowed=ROLES),
    )),
    # Derived --------------------------------------------------------------------------
    Table("oee_aggregate", "OEEAggregate", "derived",
          "OEE and its time/count components, computed only from input tables. Line and plant rows are "
          "time/count-weighted roll-ups, never averages of ratios.",
          "one row per (machine|line|plant) and shift", "aggregate_id", (
        F("aggregate_id", "STRING", pattern=P["aggregate"], unique=True),
        F("aggregate_level", "STRING", allowed=("MACHINE_SHIFT", "LINE_SHIFT", "PLANT_SHIFT")),
        F("plant_id", "STRING", fk="plant.plant_id"),
        F("line_id", "STRING", required=False, fk="line.line_id"),
        F("machine_id", "STRING", required=False, fk="machine.machine_id"),
        F("shift_id", "STRING", fk="shift.shift_id"),
        F("shift_duration_s", "INTEGER", unit="seconds"),
        F("planned_stop_s", "INTEGER", unit="seconds", desc="Breaks + planned stops (excluded from planned production time)"),
        F("planned_production_time_s", "INTEGER", unit="seconds", rule="= shift_duration_s - planned_stop_s"),
        F("unplanned_stop_s", "INTEGER", unit="seconds", desc="Stops >= micro-stop threshold and changeovers, outside breaks"),
        F("minor_stop_s", "INTEGER", unit="seconds", desc="Stops < threshold; part of run time (performance loss)"),
        F("gap_s", "INTEGER", unit="seconds", desc="Time with no state event; treated as unplanned stop"),
        F("overlap_s", "INTEGER", unit="seconds", desc="Time covered by >1 event (resolved by precedence)"),
        F("downtime_in_break_s", "INTEGER", unit="seconds", desc="Stop time reported inside a break (reclassified as planned)"),
        F("running_s", "INTEGER", unit="seconds"),
        F("run_time_s", "INTEGER", unit="seconds", rule="= running_s + minor_stop_s = PPT - unplanned_stop_s - gap_s"),
        F("total_count", "INTEGER", unit="units"),
        F("scrap_count", "INTEGER", unit="units"),
        F("rework_count", "INTEGER", unit="units"),
        F("good_count", "INTEGER", unit="units", rule="= total - scrap - rework"),
        F("ideal_run_time_s", "DECIMAL", unit="seconds", rule="= sum(total per order x standard ideal cycle time)"),
        F("availability", "DECIMAL", required=False, rule="run_time / PPT"),
        F("performance", "DECIMAL", required=False, rule="ideal_run_time / run_time"),
        F("quality", "DECIMAL", required=False, rule="good / total"),
        F("oee", "DECIMAL", required=False, rule="availability x performance x quality"),
        F("data_quality_status", "STRING", allowed=("CLEAN", "EXCEPTION", "NOT_SCHEDULED")),
        F("exception_codes", "STRING", required=False, desc="Pipe-separated exception types affecting this row"),
        F("top_loss_reason_code", "STRING", required=False, fk="downtime_reason.reason_code"),
        F("source_event_count", "INTEGER"),
        F("source_count_record_count", "INTEGER"),
        F("source_inspection_count", "INTEGER"),
        F("calc_version", "STRING"),
    )),
    Table("oee_exception", "Exception / decision log", "derived",
          "Every rule that fired during the calculation, with the record it fired on and how it was treated.",
          "one row per detected exception", "exception_id", (
        F("exception_id", "STRING", pattern=P["exception"], unique=True),
        F("issue_type", "STRING", allowed=EXCEPTION_TYPES),
        F("severity", "STRING", allowed=("INFO", "WARNING", "ERROR")),
        F("record_table", "STRING"),
        F("record_id", "STRING"),
        F("related_record_ids", "STRING", required=False),
        F("machine_id", "STRING", required=False, fk="machine.machine_id"),
        F("shift_id", "STRING", required=False, fk="shift.shift_id"),
        F("detection_rule", "STRING"),
        F("treatment", "STRING"),
        F("impact_value", "DECIMAL", required=False),
        F("impact_unit", "STRING", required=False),
    )),
    # Ground truth (never read by the calculator or validator) ---------------------------
    Table("ground_truth_anomaly", "Ground truth: injected anomalies", "ground_truth",
          "One row per deliberately injected anomaly with the rule that should catch it.",
          "one row per anomaly", "gt_id", (
        F("gt_id", "STRING", pattern=P["gt"], unique=True),
        F("issue_type", "STRING", allowed=ISSUE_TYPES),
        F("record_table", "STRING"),
        F("record_id", "STRING"),
        F("machine_id", "STRING"),
        F("shift_id", "STRING", required=False),
        F("injection", "STRING", desc="What was changed"),
        F("original_value", "STRING", required=False),
        F("injected_value", "STRING", required=False),
        F("expected_detection", "STRING"),
        F("expected_treatment", "STRING"),
    )),
    Table("ground_truth_oee", "Ground truth: expected machine-shift OEE", "ground_truth",
          "OEE components computed by the generator from its own simulation (before data-quality anomalies), "
          "via a separate code path from the calculator.", "one row per machine and shift", "machine_shift_key", (
        F("machine_shift_key", "STRING", unique=True),
        F("machine_id", "STRING"),
        F("shift_id", "STRING"),
        F("planned_production_time_s", "INTEGER"),
        F("run_time_s", "INTEGER"),
        F("total_count", "INTEGER"),
        F("good_count", "INTEGER"),
        F("ideal_run_time_s", "DECIMAL"),
        F("availability", "DECIMAL", required=False),
        F("performance", "DECIMAL", required=False),
        F("quality", "DECIMAL", required=False),
        F("oee", "DECIMAL", required=False),
    )),
    Table("ground_truth_downtime_reason", "Ground truth: true stop reasons", "ground_truth",
          "The reason the simulator actually used for each unplanned stop (to score annotations).",
          "one row per stop event", "event_id", (
        F("event_id", "STRING", unique=True),
        F("true_reason_code", "STRING"),
    )),
]

BY_NAME = {t.name: t for t in TABLES}

# Relationship documentation: (parent, child, fk column, cardinality, optional?, note)
RELATIONSHIPS = [
    ("plant", "line", "plant_id", "1:N", False, ""),
    ("plant", "shift", "plant_id", "1:N", False, "shift calendar is per plant"),
    ("line", "machine", "line_id", "1:N", False, ""),
    ("machine", "machine_product_standard", "machine_id", "1:N", False, "Machine N:M Product via this bridge"),
    ("product", "machine_product_standard", "product_id", "1:N", False, "Machine N:M Product via this bridge"),
    ("shift", "shift_break", "shift_id", "1:N (0..2)", True, "unscheduled shifts have no breaks"),
    ("machine", "production_order", "machine_id", "1:N", False, ""),
    ("product", "production_order", "product_id", "1:N", False, ""),
    ("machine_product_standard", "production_order", "standard_id", "1:N", False, "standard effective at release"),
    ("production_order", "production_order_status_event", "order_id", "1:N (1..5)", False, "append-only lifecycle"),
    ("machine", "state_event", "machine_id", "1:N", False, ""),
    ("shift", "state_event", "shift_id", "1:N", False, "events are split at shift boundaries"),
    ("production_order", "state_event", "order_id", "1:N", True, "only RUNNING/CHANGEOVER carry an order"),
    ("downtime_reason", "state_event", "reason_code", "1:N", True, "empty for RUNNING"),
    ("state_event", "downtime_annotation", "event_id", "1:N (0..2)", True, "re-annotation supersedes"),
    ("downtime_annotation", "downtime_annotation", "supersedes_annotation_id", "1:0..1", True, "self reference"),
    ("production_order", "production_count", "order_id", "1:N", False, ""),
    ("shift", "production_count", "shift_id", "1:N", False, ""),
    ("production_count", "production_count", "corrects_count_id", "1:0..N", True, "correction -> original reading"),
    ("production_order", "quality_inspection", "order_id", "1:N", False, ""),
    ("shift", "quality_inspection", "shift_id", "1:N", False, ""),
    ("shift", "oee_aggregate", "shift_id", "1:N", False, "machine, line and plant rows per shift"),
    ("machine", "oee_aggregate", "machine_id", "1:N", True, "MACHINE_SHIFT rows only"),
]
