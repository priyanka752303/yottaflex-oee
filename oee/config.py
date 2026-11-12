"""Central configuration: scale presets, fixed seed and business-rule thresholds.

Every tunable that changes the generated data or the OEE result lives here so that
reviewers can see (and change) the assumptions in one place.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date

DEFAULT_SEED = 20261022
GENERATOR_VERSION = "1.0.0"
CALC_VERSION = "1.0.0"

# Calendar ---------------------------------------------------------------------
HORIZON_START = date(2026, 1, 1)
PLANT_TIMEZONE = "Asia/Kolkata"
UTC_OFFSET = "+05:30"
# Plant holidays: no shift is scheduled on these dates.
HOLIDAYS = {date(2026, 1, 26)}  # Republic Day
# Shift calendar: code -> start hour (local). Each shift lasts 8 hours.
SHIFT_STARTS = {"A": 6, "B": 14, "C": 22}
SHIFT_LENGTH_S = 8 * 3600
# Planned breaks, as (type, offset from shift start in minutes, duration in minutes).
SHIFT_BREAKS = [("TEA", 180, 10), ("MEAL", 330, 30)]
# Night shift (C) is not scheduled on Saturday (5) and Sunday (6) nights.
UNSCHEDULED_C_WEEKDAYS = {5, 6}

# OEE rules ------------------------------------------------------------------------
# A STOPPED event shorter than this is a "minor stop": it stays inside run time and
# shows up as a performance loss (six-big-losses convention), not an availability loss.
MICRO_STOP_THRESHOLD_S = 120
# Order is COMPLETED when counted good+bad output reaches this share of planned qty,
# otherwise CLOSED_SHORT.
ORDER_COMPLETION_RATIO = 0.98
# Ideal cycle time on an order may differ from the master standard by rounding only.
ICT_TOLERANCE_S = 0.05

# Share of count records that are later corrected by a manual correction record.
CORRECTION_RATE = 0.004


@dataclass(frozen=True)
class Scale:
    name: str
    lines: int
    machines_per_line: int
    products_per_line: int
    days: int
    target_state_events: int
    target_count_inspection_records: int
    anomalies_per_type: int

    @property
    def machines(self) -> int:
        return self.lines * self.machines_per_line

    @property
    def products(self) -> int:
        return self.lines * self.products_per_line

    def as_dict(self) -> dict:
        d = asdict(self)
        d["machines"] = self.machines
        d["products"] = self.products
        return d


FULL = Scale("full", lines=5, machines_per_line=6, products_per_line=4, days=90,
             target_state_events=100_000, target_count_inspection_records=500_000,
             anomalies_per_type=25)

# Densities of the full dataset, reused so that every scale has the same "texture".
_EVENTS_PER_MACHINE_DAY = FULL.target_state_events / (FULL.machines * FULL.days)
_RECORDS_PER_MACHINE_DAY = FULL.target_count_inspection_records / (FULL.machines * FULL.days)


def make_scale(name: str, lines: int, machines_per_line: int, products_per_line: int,
               days: int, anomalies_per_type: int) -> Scale:
    machine_days = lines * machines_per_line * days
    return Scale(name, lines, machines_per_line, products_per_line, days,
                 target_state_events=round(_EVENTS_PER_MACHINE_DAY * machine_days),
                 target_count_inspection_records=round(_RECORDS_PER_MACHINE_DAY * machine_days),
                 anomalies_per_type=anomalies_per_type)


STARTER = make_scale("starter", lines=2, machines_per_line=3, products_per_line=3, days=14,
                     anomalies_per_type=3)
TINY = make_scale("tiny", lines=1, machines_per_line=3, products_per_line=3, days=7,
                  anomalies_per_type=2)

SCALES = {s.name: s for s in (FULL, STARTER, TINY)}
