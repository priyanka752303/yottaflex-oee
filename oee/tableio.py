"""CSV read/write driven by the schema (stable column order, stable value formatting)."""
from __future__ import annotations

import csv
import os

from .schema import BY_NAME


def fmt_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(round(v, 6))
    return str(v)


def write_table(directory: str, name: str, rows: list[dict]) -> str:
    table = BY_NAME[name]
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.csv")
    cols = table.columns
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([fmt_value(r.get(c)) for c in cols])
    return path


def read_table(directory: str, name: str) -> list[dict]:
    path = os.path.join(directory, f"{name}.csv")
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def typed(name: str, row: dict) -> dict:
    """Convert a CSV row (all strings) to typed Python values using the schema."""
    table = BY_NAME[name]
    out = {}
    for f in table.fields:
        raw = row.get(f.name, "")
        if raw == "" or raw is None:
            out[f.name] = None
        elif f.type == "INTEGER":
            out[f.name] = int(raw)
        elif f.type == "DECIMAL":
            out[f.name] = float(raw)
        elif f.type == "BOOLEAN":
            out[f.name] = raw == "true"
        else:
            out[f.name] = raw
    return out
