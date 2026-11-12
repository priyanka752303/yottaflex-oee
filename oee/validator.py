"""Validation of inputs and derived outputs. Never reads ground truth.

Structural checks (must be zero failures): types, required, enums, ID patterns, PK uniqueness,
FK integrity. Temporal/lifecycle/duplicate checks and arithmetic reconciliation follow.
Expected data exceptions (the labelled anomalies) are reported separately as findings, not failures.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict

from . import config as C
from .ids import parse_ts
from .schema import BY_NAME, ORDER_TRANSITIONS, TABLES
from .tableio import read_table


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, category, checked, failures, note=""):
        self.checks.append(dict(check=name, category=category, status="PASS" if not failures else "FAIL",
                                checked=checked, failures=len(failures), sample=failures[:5], note=note))


def _type_ok(f, v):
    try:
        if f.type == "INTEGER":
            int(v)
        elif f.type == "DECIMAL":
            float(v)
        elif f.type == "BOOLEAN":
            return v in ("true", "false")
        elif f.type == "TIMESTAMP":
            parse_ts(v)
        elif f.type == "DATE":
            return re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is not None
        return True
    except ValueError:
        return False


def structural(rep: Report, data: dict):
    pk_values = {}
    for t in TABLES:
        if t.name not in data:
            continue
        rows = data[t.name]
        type_f, req_f, enum_f, pat_f = [], [], [], []
        pats = {f.name: re.compile(f.pattern) for f in t.fields if f.pattern}
        for r in rows:
            for f in t.fields:
                v = r.get(f.name, "")
                if v == "":
                    if f.required:
                        req_f.append(f"{r[t.pk]}.{f.name}")
                    continue
                if not _type_ok(f, v):
                    type_f.append(f"{r[t.pk]}.{f.name}={v}")
                if f.allowed and v not in f.allowed:
                    enum_f.append(f"{r[t.pk]}.{f.name}={v}")
                if f.name in pats and not pats[f.name].match(v):
                    pat_f.append(f"{r[t.pk]}.{f.name}={v}")
        n = len(rows) * len(t.fields)
        rep.add(f"{t.name}: data types", "STRUCTURE", n, type_f)
        rep.add(f"{t.name}: required fields", "STRUCTURE", n, req_f)
        rep.add(f"{t.name}: allowed values", "STRUCTURE", n, enum_f)
        if pats:
            rep.add(f"{t.name}: ID / code format", "STRUCTURE", len(rows) * len(pats), pat_f)
        seen, dups = set(), []
        for r in rows:
            if r[t.pk] in seen:
                dups.append(r[t.pk])
            seen.add(r[t.pk])
        pk_values[t.name] = seen
        rep.add(f"{t.name}: primary key unique", "STRUCTURE", len(rows), dups)
    for t in TABLES:
        if t.name not in data:
            continue
        for f in t.fields:
            if not f.fk:
                continue
            ptable, pcol = f.fk.split(".")
            if ptable not in data:
                continue
            parents = pk_values[ptable] if BY_NAME[ptable].pk == pcol else {r[pcol] for r in data[ptable]}
            bad = [f"{r[t.pk]}.{f.name}={r[f.name]}" for r in data[t.name] if r[f.name] and r[f.name] not in parents]
            rep.add(f"{t.name}.{f.name} -> {f.fk}", "FOREIGN_KEY", len(data[t.name]), bad)


def temporal_and_lifecycle(rep: Report, d: dict):
    shifts = {s["shift_id"]: s for s in d["shift"]}
    win = {k: (parse_ts(s["start_ts"]), parse_ts(s["end_ts"])) for k, s in shifts.items()}
    bad = [s["shift_id"] for s in d["shift"]
           if win[s["shift_id"]][1] - win[s["shift_id"]][0] != int(s["duration_s"]) or int(s["duration_s"]) <= 0]
    rep.add("shift: end > start and duration = end - start", "TEMPORAL", len(d["shift"]), bad)
    ordered = sorted(win.values())
    bad = [i for i in range(1, len(ordered)) if ordered[i][0] != ordered[i - 1][1]]
    rep.add("shift calendar contiguous, no overlap", "TEMPORAL", len(ordered), bad)
    bad = [b["break_id"] for b in d["shift_break"]
           if not (win[b["shift_id"]][0] <= parse_ts(b["start_ts"]) < parse_ts(b["end_ts"]) <= win[b["shift_id"]][1])]
    rep.add("shift_break inside its shift", "TEMPORAL", len(d["shift_break"]), bad)

    bad_order, bad_dur, bad_in = [], [], []
    for e in d["state_event"]:
        s, t = parse_ts(e["start_ts"]), parse_ts(e["end_ts"])
        if t <= s:
            bad_order.append(e["event_id"])
        if t - s != int(e["duration_s"]):
            bad_dur.append(e["event_id"])
        ws, we = win[e["shift_id"]]
        if not (ws <= s and t <= we):
            bad_in.append(e["event_id"])
    rep.add("state_event: end > start", "TEMPORAL", len(d["state_event"]), bad_order)
    rep.add("state_event: duration = end - start", "RECONCILIATION", len(d["state_event"]), bad_dur)
    rep.add("state_event inside its shift", "TEMPORAL", len(d["state_event"]), bad_in)
    bad = [e["event_id"] for e in d["state_event"]
           if (e["state"] == "RUNNING") != (e["reason_code"] == "")
           or (e["state"] in ("RUNNING", "CHANGEOVER") and not e["order_id"])]
    rep.add("state_event: reason/order presence by state", "STRUCTURE", len(d["state_event"]), bad)
    seq = defaultdict(list)
    for e in d["state_event"]:
        seq[e["machine_id"]].append((e["event_id"], parse_ts(e["start_ts"])))
    bad = [m for m, v in seq.items() if [x[1] for x in sorted(v)] != sorted(x[1] for x in v)]
    rep.add("state_event IDs ordered by start time per machine", "STRUCTURE", len(seq), bad)

    std = {s["standard_id"]: s for s in d["machine_product_standard"]}
    bad = [s["standard_id"] for s in std.values()
           if s["effective_to"] and parse_ts(s["effective_to"]) <= parse_ts(s["effective_from"])]
    rep.add("standard: effective_to > effective_from", "TEMPORAL", len(std), bad)
    versions = defaultdict(list)
    for s in std.values():
        versions[(s["machine_id"], s["product_id"])].append(s)
    bad = []
    for k, vs in versions.items():
        vs.sort(key=lambda s: int(s["version"]))
        for a, b in zip(vs, vs[1:]):
            if not a["effective_to"] or parse_ts(a["effective_to"]) > parse_ts(b["effective_from"]):
                bad.append(b["standard_id"])
    rep.add("standard versions do not overlap", "TEMPORAL", len(versions), bad)
    machines_on_line = {m["machine_id"]: m["line_id"] for m in d["machine"]}
    fam_line = {l["line_id"]: l["product_family"] for l in d["line"]}
    fam_prod = {p["product_id"]: p["product_family"] for p in d["product"]}
    bad = [s["standard_id"] for s in std.values() if fam_prod[s["product_id"]] != fam_line[machines_on_line[s["machine_id"]]]]
    rep.add("standard: product family matches machine's line", "RECONCILIATION", len(std), bad)

    orders = {o["order_id"]: o for o in d["production_order"]}
    bad_std, bad_eff, bad_time = [], [], []
    for o in orders.values():
        s = std[o["standard_id"]]
        if s["machine_id"] != o["machine_id"] or s["product_id"] != o["product_id"]:
            bad_std.append(o["order_id"])
        ref = parse_ts(o["released_ts"] or o["created_ts"])
        if not (parse_ts(s["effective_from"]) <= ref and (not s["effective_to"] or ref < parse_ts(s["effective_to"]))):
            bad_eff.append(o["order_id"])
        chain = [o["created_ts"], o["released_ts"], o["actual_start_ts"], o["actual_end_ts"]]
        ts = [parse_ts(x) for x in chain if x]
        if ts != sorted(ts) or parse_ts(o["planned_end_ts"]) <= parse_ts(o["planned_start_ts"]):
            bad_time.append(o["order_id"])
    rep.add("order: standard matches machine+product", "FOREIGN_KEY", len(orders), bad_std)
    rep.add("order: standard effective at release", "TEMPORAL", len(orders), bad_eff)
    rep.add("order: created <= released <= started <= ended; planned_end > planned_start", "TEMPORAL", len(orders), bad_time)

    hist = defaultdict(list)
    for h in d["production_order_status_event"]:
        hist[h["order_id"]].append(h)
    bad_tr, bad_cur = [], []
    for oid, hs in hist.items():
        hs.sort(key=lambda h: h["status_event_id"])
        prev, prev_ts = None, None
        for h in hs:
            frm = h["from_status"] or None
            if frm != prev or h["to_status"] not in ORDER_TRANSITIONS[prev] or (
                    prev_ts is not None and parse_ts(h["changed_ts"]) < prev_ts):
                bad_tr.append(h["status_event_id"])
            prev, prev_ts = h["to_status"], parse_ts(h["changed_ts"])
        if orders[oid]["current_status"] != prev:
            bad_cur.append(oid)
    rep.add("order lifecycle transitions valid and time-ordered", "LIFECYCLE", len(hist), bad_tr)
    rep.add("order current_status = latest status event", "LIFECYCLE", len(orders), bad_cur)
    rep.add("every order has lifecycle history", "LIFECYCLE", len(orders), [o for o in orders if o not in hist])

    events = {e["event_id"]: e for e in d["state_event"]}
    anns = {a["annotation_id"]: a for a in d["downtime_annotation"]}
    bad = []
    for a in anns.values():
        e = events[a["event_id"]]
        sup = anns.get(a["supersedes_annotation_id"]) if a["supersedes_annotation_id"] else None
        if (e["state"] != "STOPPED" or parse_ts(a["annotated_ts"]) < parse_ts(e["end_ts"])
                or (sup and (sup["event_id"] != a["event_id"] or parse_ts(sup["annotated_ts"]) > parse_ts(a["annotated_ts"])))):
            bad.append(a["annotation_id"])
    rep.add("annotation: on a STOPPED event, after it ends, supersedes same event", "LIFECYCLE", len(anns), bad)

    counts = {c["count_id"]: c for c in d["production_count"]}
    bad_m, bad_corr, bad_ts = [], [], []
    for c in counts.values():
        if orders[c["order_id"]]["machine_id"] != c["machine_id"]:
            bad_m.append(c["count_id"])
        if c["record_type"] == "MANUAL_CORRECTION":
            o = counts.get(c["corrects_count_id"])
            if (not o or o["record_type"] != "PLC_READING" or o["order_id"] != c["order_id"]
                    or o["shift_id"] != c["shift_id"] or parse_ts(c["record_ts"]) < parse_ts(o["record_ts"])):
                bad_corr.append(c["count_id"])
        else:
            ws, we = win[c["shift_id"]]
            if not ws < parse_ts(c["record_ts"]) <= we:
                bad_ts.append(c["count_id"])
            if c["corrects_count_id"]:
                bad_corr.append(c["count_id"])
    rep.add("count: machine = order's machine", "FOREIGN_KEY", len(counts), bad_m)
    rep.add("count: correction points at an earlier reading of the same order and shift", "LIFECYCLE",
            len(counts), bad_corr)
    rep.add("count: reading timestamp inside its shift", "TEMPORAL", len(counts), bad_ts)
    insp = d["quality_inspection"]
    bad = [q["inspection_id"] for q in insp if q["inspection_type"] == "SAMPLE" and int(q["defects_found"]) > int(q["sample_size"])]
    rep.add("inspection: defects_found <= sample_size", "RECONCILIATION", len(insp), bad)
    bad = [q["inspection_id"] for q in insp if orders[q["order_id"]]["machine_id"] != q["machine_id"]]
    rep.add("inspection: machine = order's machine", "FOREIGN_KEY", len(insp), bad)

    # duplicates
    def dup_check(name, rows, key):
        seen, dups = set(), []
        for r in rows:
            k = key(r)
            if k in seen:
                dups.append("|".join(k))
            seen.add(k)
        rep.add(name, "DUPLICATES", len(rows), dups)
    dup_check("duplicate state events (machine, start, end, state)", d["state_event"],
              lambda e: (e["machine_id"], e["start_ts"], e["end_ts"], e["state"]))
    dup_check("duplicate PLC readings (order, ts, counter)",
              [c for c in d["production_count"] if c["record_type"] == "PLC_READING"],
              lambda c: (c["order_id"], c["record_ts"], c["counter_value"]))
    dup_check("duplicate lot dispositions (order, shift)",
              [q for q in insp if q["inspection_type"] == "LOT_DISPOSITION"], lambda q: (q["order_id"], q["shift_id"]))
    dup_check("duplicate annotations (event, ts, reason)", d["downtime_annotation"],
              lambda a: (a["event_id"], a["annotated_ts"], a["reason_code"]))


def reconciliation(rep: Report, d: dict):
    aggs = d["oee_aggregate"]
    f = lambda r, k: int(r[k])
    bad_time, bad_ppt, bad_run, bad_good, bad_ratio, bad_bounds = [], [], [], [], [], []
    for r in aggs:
        if (f(r, "planned_stop_s") + f(r, "unplanned_stop_s") + f(r, "minor_stop_s") + f(r, "running_s")
                + f(r, "gap_s")) != f(r, "shift_duration_s"):
            bad_time.append(r["aggregate_id"])
        if f(r, "planned_production_time_s") != f(r, "shift_duration_s") - f(r, "planned_stop_s"):
            bad_ppt.append(r["aggregate_id"])
        if not (f(r, "run_time_s") == f(r, "running_s") + f(r, "minor_stop_s")
                == f(r, "planned_production_time_s") - f(r, "unplanned_stop_s") - f(r, "gap_s")):
            bad_run.append(r["aggregate_id"])
        if f(r, "good_count") != f(r, "total_count") - f(r, "scrap_count") - f(r, "rework_count"):
            bad_good.append(r["aggregate_id"])
        ppt, run, tot = f(r, "planned_production_time_s"), f(r, "run_time_s"), f(r, "total_count")
        a = run / ppt if ppt else None
        p = float(r["ideal_run_time_s"]) / run if run else None
        q = f(r, "good_count") / tot if tot else None
        o = None if a is None else (0.0 if a == 0 else (a * p * q if p is not None and q is not None else None))
        for name, val in (("availability", a), ("performance", p), ("quality", q), ("oee", o)):
            got = r[name]
            if (val is None) != (got == "") or (val is not None and abs(float(got) - val) > 1e-6):
                bad_ratio.append(f"{r['aggregate_id']}.{name}")
        for name in ("availability", "quality"):
            if r[name] and not 0 <= float(r[name]) <= 1:
                bad_bounds.append(f"{r['aggregate_id']}.{name}")
    rep.add("aggregate: planned + unplanned + minor + running + gap = shift length", "RECONCILIATION", len(aggs), bad_time)
    rep.add("aggregate: PPT = shift length - planned stops", "RECONCILIATION", len(aggs), bad_ppt)
    rep.add("aggregate: run time = running + minor = PPT - unplanned - gap", "RECONCILIATION", len(aggs), bad_run)
    rep.add("aggregate: good = total - scrap - rework", "RECONCILIATION", len(aggs), bad_good)
    rep.add("aggregate: A, P, Q, OEE recomputed from stored components", "RECONCILIATION", len(aggs) * 4, bad_ratio)
    rep.add("aggregate: availability and quality within [0, 1]", "RECONCILIATION", len(aggs) * 2, bad_bounds)

    ms = [r for r in aggs if r["aggregate_level"] == "MACHINE_SHIFT"]
    by_line, by_plant = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    keys = ["planned_production_time_s", "run_time_s", "total_count", "good_count", "ideal_run_time_s"]
    for r in ms:
        for k in keys:
            by_line[(r["line_id"], r["shift_id"])][k] += float(r[k])
            by_plant[r["shift_id"]][k] += float(r[k])
    bad = []
    for r in aggs:
        if r["aggregate_level"] == "MACHINE_SHIFT":
            continue
        src = by_line[(r["line_id"], r["shift_id"])] if r["aggregate_level"] == "LINE_SHIFT" else by_plant[r["shift_id"]]
        if any(abs(float(r[k]) - src[k]) > 0.01 for k in keys):
            bad.append(r["aggregate_id"])
    rep.add("roll-ups equal the sum of their machine-shift components", "RECONCILIATION", len(aggs) - len(ms), bad)
    n_machines, n_shifts = len(d["machine"]), len(d["shift"])
    rep.add("one machine-shift aggregate per machine x shift", "RECONCILIATION", len(ms),
            [] if len(ms) == n_machines * n_shifts else [f"{len(ms)} != {n_machines * n_shifts}"])

    # counts: aggregate totals == valid counter increments + corrections (recomputed here independently)
    reads = defaultdict(list)
    corr = defaultdict(int)
    for c in d["production_count"]:
        if c["record_type"] == "PLC_READING":
            reads[c["order_id"]].append((parse_ts(c["record_ts"]), c["count_id"], int(c["counter_value"]), c["shift_id"],
                                         int(c["increment_qty"])))
        else:
            corr[(c["machine_id"], c["shift_id"])] += int(c["increment_qty"])
    tot = defaultdict(int)
    bad_inc = []
    order_total = defaultdict(int)
    for oid, rs in reads.items():
        hi = 0
        for ts, cid, counter, sid, inc in sorted(rs):
            if counter < hi:
                continue
            if inc != counter - hi:
                bad_inc.append(cid)
            tot[(oid, sid)] += counter - hi
            order_total[oid] += counter - hi
            hi = counter
    ms_tot = defaultdict(int)
    machine_of = {o["order_id"]: o["machine_id"] for o in d["production_order"]}
    for (oid, sid), v in tot.items():
        ms_tot[(machine_of[oid], sid)] += v
    for k, v in corr.items():
        ms_tot[k] += v
    for c in d["production_count"]:
        if c["record_type"] == "MANUAL_CORRECTION":
            order_total[c["order_id"]] += int(c["increment_qty"])
    bad = [r["aggregate_id"] for r in ms if int(r["total_count"]) != ms_tot.get((r["machine_id"], r["shift_id"]), 0)]
    rep.add("count: increment_qty = counter - previous valid reading", "RECONCILIATION",
            sum(len(v) for v in reads.values()), bad_inc)
    rep.add("aggregate total_count = valid increments + corrections", "RECONCILIATION", len(ms), bad)
    bad = []
    for o in d["production_order"]:
        if o["current_status"] in ("COMPLETED", "CLOSED_SHORT"):
            expect = "COMPLETED" if order_total[o["order_id"]] >= C.ORDER_COMPLETION_RATIO * int(o["planned_qty"]) else "CLOSED_SHORT"
            if expect != o["current_status"]:
                bad.append(o["order_id"])
    rep.add("order final status derived from counted quantity", "RECONCILIATION", len(d["production_order"]), bad)
    sched = {s["shift_id"]: s["is_production_scheduled"] == "true" for s in d["shift"]}
    bad = [r["aggregate_id"] for r in ms if not sched[r["shift_id"]] and (r["oee"] != "" or r["data_quality_status"] != "NOT_SCHEDULED")]
    rep.add("unscheduled shifts: PPT = 0, OEE empty, status NOT_SCHEDULED", "RECONCILIATION", len(ms), bad)


def validate(base_dir: str) -> dict:
    data = {}
    for t in TABLES:
        if t.layer == "ground_truth":
            continue
        data[t.name] = read_table(os.path.join(base_dir, t.layer), t.name)
    rep = Report()
    structural(rep, data)
    temporal_and_lifecycle(rep, data)
    reconciliation(rep, data)
    findings = defaultdict(int)
    for x in data["oee_exception"]:
        findings[x["issue_type"]] += 1
    summary = dict(
        checks_total=len(rep.checks), checks_passed=sum(c["status"] == "PASS" for c in rep.checks),
        checks_failed=sum(c["status"] == "FAIL" for c in rep.checks),
        row_counts={k: len(v) for k, v in data.items()},
        data_exceptions_found=dict(sorted(findings.items())),
        note="Data exceptions are expected labelled anomalies; they are detected and treated by the calculator "
             "and are not validation failures.",
        checks=rep.checks)
    out = os.path.join(base_dir, "reports")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "validation_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    with open(os.path.join(out, "validation_summary.md"), "w") as fh:
        fh.write(f"# Validation summary\n\n{summary['checks_passed']}/{summary['checks_total']} checks passed.\n\n")
        fh.write("Data exceptions detected (expected, labelled anomalies plus informational findings):\n\n")
        for k, v in summary["data_exceptions_found"].items():
            fh.write(f"- {k}: {v}\n")
        fh.write("\n| Status | Category | Check | Checked | Failures |\n|---|---|---|---:|---:|\n")
        for c in rep.checks:
            fh.write(f"| {c['status']} | {c['category']} | {c['check']} | {c['checked']} | {c['failures']} |\n")
    return summary
