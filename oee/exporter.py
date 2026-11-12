"""Exports (JSON Lines, SQL DDL + seed, SQLite), the source manifest with checksums,
and generated documentation (data dictionary, ERD)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3

from . import config as C
from .schema import BY_NAME, RELATIONSHIPS, TABLES
from .tableio import read_table, typed

SQL_TYPES = {"STRING": "TEXT", "INTEGER": "INTEGER", "DECIMAL": "REAL", "TIMESTAMP": "TEXT", "DATE": "TEXT",
             "BOOLEAN": "INTEGER"}


def ddl() -> str:
    out = ["-- Generated from oee/schema.py. Timestamps are ISO-8601 with UTC offset; booleans are 0/1.",
           "PRAGMA foreign_keys = ON;", ""]
    for t in TABLES:
        cols = []
        for f in t.fields:
            c = f"  {f.name} {SQL_TYPES[f.type]}"
            if f.name == t.pk:
                c += " PRIMARY KEY"
            elif f.required:
                c += " NOT NULL"
            if f.allowed:
                vals = ", ".join(f"'{v}'" for v in f.allowed)
                c += f" CHECK ({f.name} IN ({vals}))"
            cols.append(c)
        for f in t.fields:
            if f.fk:
                pt, pc = f.fk.split(".")
                cols.append(f"  FOREIGN KEY ({f.name}) REFERENCES {pt}({pc}) DEFERRABLE INITIALLY DEFERRED")
        out.append(f"-- {t.entity}: {t.description}\nCREATE TABLE {t.name} (\n" + ",\n".join(cols) + "\n);\n")
    return "\n".join(out)


def _sql_lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _load(base_dir):
    data = {}
    for t in TABLES:
        path = os.path.join(base_dir, t.layer, f"{t.name}.csv")
        if os.path.exists(path):
            data[t.name] = [typed(t.name, r) for r in read_table(os.path.join(base_dir, t.layer), t.name)]
    return data


def export(base_dir: str, formats=("json", "sql", "sqlite")) -> dict:
    data = _load(base_dir)
    exp = os.path.join(base_dir, "export")
    result = {}
    if "json" in formats:
        jd = os.path.join(exp, "json")
        os.makedirs(jd, exist_ok=True)
        for name, rows in data.items():
            with open(os.path.join(jd, f"{name}.jsonl"), "w") as fh:
                for r in rows:
                    fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        result["json"] = len(data)
    if "sql" in formats or "sqlite" in formats:
        sd = os.path.join(exp, "sql")
        os.makedirs(sd, exist_ok=True)
        with open(os.path.join(sd, "schema.sql"), "w") as fh:
            fh.write(ddl())
    if "sql" in formats:
        with open(os.path.join(exp, "sql", "seed.sql"), "w") as fh:
            fh.write("-- Seed data. Load after schema.sql, e.g. sqlite3 oee.db < schema.sql < seed.sql\nBEGIN;\n")
            for t in TABLES:
                if t.name not in data:
                    continue
                cols = t.columns
                rows = data[t.name]
                for i in range(0, len(rows), 500):
                    vals = ",\n".join("(" + ",".join(_sql_lit(r[c]) for c in cols) + ")" for r in rows[i:i + 500])
                    fh.write(f"INSERT INTO {t.name} ({','.join(cols)}) VALUES\n{vals};\n")
            fh.write("COMMIT;\n")
        result["sql"] = True
    if "sqlite" in formats:
        path = os.path.join(exp, "oee.sqlite")
        if os.path.exists(path):
            os.remove(path)
        con = sqlite3.connect(path)
        con.executescript(ddl())
        con.execute("BEGIN")
        for t in TABLES:
            if t.name in data:
                q = f"INSERT INTO {t.name} VALUES ({','.join('?' * len(t.columns))})"
                con.executemany(q, [tuple(r[c] for c in t.columns) for r in data[t.name]])
        con.commit()
        fk_violations = con.execute("PRAGMA foreign_key_check").fetchall()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        con.close()
        result["sqlite"] = dict(foreign_key_violations=len(fk_violations), integrity=integrity)
        os.makedirs(os.path.join(base_dir, "reports"), exist_ok=True)
        with open(os.path.join(base_dir, "reports", "sqlite_load_check.json"), "w") as fh:
            json.dump(result["sqlite"], fh, indent=2)
    return result


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(base_dir: str, scale: C.Scale, seed: int, command: str) -> dict:
    """Source manifest. Covers every deterministic artefact (the SQLite binary is excluded because
    its page layout is not guaranteed byte-identical across SQLite builds)."""
    files = []
    for root, _dirs, names in os.walk(base_dir):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, base_dir)
            if n.endswith(".sqlite") or rel in ("manifest.json", "reports/reproducibility.json"):
                continue
            rows = None
            if n.endswith(".csv") or n.endswith(".jsonl"):
                with open(p, "rb") as fh:
                    rows = sum(1 for _ in fh) - (1 if n.endswith(".csv") else 0)
            files.append(dict(path=rel, rows=rows, bytes=os.path.getsize(p), sha256=sha256(p)))
    files.sort(key=lambda f: f["path"])
    m = dict(generator_version=C.GENERATOR_VERSION, calc_version=C.CALC_VERSION, seed=seed, scale=scale.as_dict(),
             command=command, python=platform.python_version(),
             external_data_sources=[], provenance="100% synthetic; no external or personal data used",
             files=files,
             dataset_checksum=hashlib.sha256("".join(f["sha256"] for f in files).encode()).hexdigest())
    with open(os.path.join(base_dir, "manifest.json"), "w") as fh:
        json.dump(m, fh, indent=2)
    return m


def data_dictionary_md() -> str:
    out = ["# Data dictionary", "",
           "Generated from `oee/schema.py` (`python -m oee docs`). The same definitions drive the SQL DDL and "
           "the structural validation, so this document cannot drift from the code.", "",
           "Conventions: timestamps are ISO-8601 local plant time with offset (`+05:30`, Asia/Kolkata); "
           "intervals are half-open `[start, end)`; durations are integer seconds; empty CSV cell = null.", ""]
    for layer, title in (("input", "Input (source) tables"), ("derived", "Derived tables"),
                         ("ground_truth", "Ground truth (evaluation only, never read by the calculator)")):
        out += [f"## {title}", ""]
        for t in TABLES:
            if t.layer != layer:
                continue
            out += [f"### `{t.name}` - {t.entity}", "", t.description, "",
                    f"- Grain: {t.grain}", f"- Primary key: `{t.pk}`"]
            if t.lifecycle:
                out.append(f"- Lifecycle: {t.lifecycle}")
            if t.effective_dating:
                out.append(f"- Effective dating: {t.effective_dating}")
            out += ["", "| Field | Type | Req. | Allowed values / format | Unit | Unique | FK | Validation rule / notes |",
                    "|---|---|---|---|---|---|---|---|"]
            for f in t.fields:
                allowed = ", ".join(f.allowed) if f.allowed else (f"`{f.pattern}`" if f.pattern else "")
                note = "; ".join(x for x in (f.desc, f.rule) if x)
                out.append(f"| `{f.name}` | {f.type} | {'Y' if f.required else 'N'} | {allowed} | {f.unit or ''} | "
                           f"{'Y' if f.unique or f.name == t.pk else ''} | {f.fk or ''} | {note} |")
            out.append("")
    out += ["## Relationships and cardinality", "",
            "| Parent | Child | FK column | Cardinality | Optional | Note |", "|---|---|---|---|---|---|"]
    for p, c, col, card, opt, note in RELATIONSHIPS:
        out.append(f"| {p} | {c} | `{col}` | {card} | {'yes' if opt else 'no'} | {note} |")
    return "\n".join(out) + "\n"


def erd_md() -> str:
    lines = ["# Entity relationship diagram", "", "Generated from `oee/schema.py`.", "", "```mermaid", "erDiagram"]
    sym = {"1:N": "||--o{", "1:N (0..2)": "||--o{", "1:N (1..5)": "||--|{", "1:0..1": "|o--o|", "1:0..N": "|o--o{"}
    for p, c, col, card, opt, _ in RELATIONSHIPS:
        lines.append(f"    {p} {sym.get(card, '||--o{')} {c} : \"{col}\"")
    for t in TABLES:
        if t.layer == "ground_truth":
            continue
        lines.append(f"    {t.name} {{")
        for f in t.fields:
            tag = " PK" if f.name == t.pk else (" FK" if f.fk else "")
            lines.append(f"        {SQL_TYPES[f.type].lower()} {f.name}{tag}")
        lines.append("    }")
    lines.append("```")
    return "\n".join(lines) + "\n"


def write_docs(docs_dir: str):
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "DATA_DICTIONARY.md"), "w") as fh:
        fh.write(data_dictionary_md())
    with open(os.path.join(docs_dir, "ERD.md"), "w") as fh:
        fh.write(erd_md())
    with open(os.path.join(docs_dir, "schema.sql"), "w") as fh:
        fh.write(ddl())
