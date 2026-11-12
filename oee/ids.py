"""Deterministic ID builders, ID patterns and timestamp helpers.

Internally every timestamp is an integer number of seconds since the plant-local
midnight of HORIZON_START. Files carry ISO-8601 timestamps with the plant UTC offset.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date
from functools import lru_cache

from .config import HORIZON_START, UTC_OFFSET

_TZ = datetime.strptime(UTC_OFFSET, "%z").tzinfo
T0 = datetime(HORIZON_START.year, HORIZON_START.month, HORIZON_START.day, tzinfo=_TZ)


def fmt_ts(sec: int | None) -> str:
    if sec is None:
        return ""
    return (T0 + timedelta(seconds=int(sec))).isoformat()


@lru_cache(maxsize=None)
def parse_ts(s: str) -> int:
    return int((datetime.fromisoformat(s) - T0).total_seconds())


def day_offset(d: date) -> int:
    return (d - HORIZON_START).days * 86400


# ID builders ------------------------------------------------------------------------
def plant_id(n: int) -> str: return f"PLT-{n:02d}"
def line_id(n: int) -> str: return f"LINE-{n:02d}"
def machine_id(n: int) -> str: return f"MC-{n:03d}"
def product_id(n: int) -> str: return f"PRD-{n:03d}"
def standard_id(m: str, p: str, v: int) -> str: return f"STD-{m}-{p}-V{v}"
def shift_id(d: date, code: str) -> str: return f"SHIFT-{d.isoformat()}-{code}"
def break_id(shift: str, n: int) -> str: return f"BRK-{shift[6:]}-{n}"
def order_id(n: int) -> str: return f"PO-2026-{n:06d}"
def order_status_event_id(order: str, n: int) -> str: return f"POS-{order[3:]}-{n:02d}"
def event_id(machine: str, n: int) -> str: return f"EVT-{machine}-{n:06d}"
def count_id(order: str, n: int) -> str: return f"CNT-{order}-{n:06d}"
def qc_id(n: int) -> str: return f"QC-2026-{n:06d}"
def annotation_id(n: int) -> str: return f"ANN-2026-{n:06d}"
def gt_id(n: int) -> str: return f"GT-2026-{n:06d}"
def exception_id(n: int) -> str: return f"EXC-2026-{n:06d}"


PATTERNS = {
    "plant": r"^PLT-\d{2}$",
    "line": r"^LINE-\d{2}$",
    "machine": r"^MC-\d{3}$",
    "product": r"^PRD-\d{3}$",
    "standard": r"^STD-MC-\d{3}-PRD-\d{3}-V\d+$",
    "shift": r"^SHIFT-\d{4}-\d{2}-\d{2}-[ABC]$",
    "break": r"^BRK-\d{4}-\d{2}-\d{2}-[ABC]-\d$",
    "order": r"^PO-2026-\d{6}$",
    "order_status_event": r"^POS-2026-\d{6}-\d{2}$",
    "event": r"^EVT-MC-\d{3}-\d{6}$",
    "count": r"^CNT-PO-2026-\d{6}-\d{6}$",
    "qc": r"^QC-2026-\d{6}$",
    "annotation": r"^ANN-2026-\d{6}$",
    "reason": r"^DR-[A-Z]+(-[A-Z]+)?$",
    "gt": r"^GT-2026-\d{6}$",
    "exception": r"^EXC-2026-\d{6}$",
    "aggregate": r"^OEE-(MS|LS|PS)-[A-Z0-9-]+$",
}
