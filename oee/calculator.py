"""OEE calculator. Reads ONLY the input tables (never ground truth) and writes:

  derived/oee_aggregate.csv  - machine/line/plant x shift OEE with every time/count component
  derived/oee_exception.csv  - decision log: which rule fired, on which record, and the treatment

Rules (see docs/DESIGN.md for the reasoning):
  * Planned production time (PPT) = shift length - planned stops. Planned stops are the shift's
    break windows (whatever the machine reported) plus PLANNED_STOP events.
  * STOPPED events shorter than MICRO_STOP_THRESHOLD_S are minor stops: inside run time,
    so they reduce Performance, not Availability. Longer stops and CHANGEOVER reduce Availability.
  * Time with no event is a gap: treated as unplanned stop and flagged.
  * Time covered by >1 event is resolved PLANNED_STOP > STOPPED > CHANGEOVER > RUNNING and flagged.
  * Total count comes from the PLC counter sequence per order: a reading below the running maximum
    with no correction pointing at it is quarantined. Manual corrections add their signed
    adjustment to the shift of the reading they correct. Originals are never modified.
  * Ideal time uses the master standard referenced by the order, not the order's snapshot.
  * A lot disposition whose scrap+rework exceeds the counted lot total is quarantined.
  * Availability = run/PPT, Performance = ideal/run, Quality = good/total, OEE = A x P x Q.
"""
from __future__ import annotations

import os
from collections import defaultdict

from . import config as C
from . import ids
from .ids import parse_ts
from .tableio import read_table, write_table

PRECEDENCE = {"PLANNED_STOP": 4, "STOPPED": 3, "CHANGEOVER": 2, "RUNNING": 1}


def classify_machine_shift(events, breaks, start, end, threshold=C.MICRO_STOP_THRESHOLD_S):
    """Time accounting for one machine in one shift.

    events: list of dicts with event_id, state, s, e (ints), reason
    breaks: list of (s, e)
    Returns (components dict, overlaps [(primary_event, other_event, seconds)],
             break_hits {event_id: seconds}, loss_by_reason {reason: seconds}).
    """
    pts = {start, end}
    for ev in events:
        pts.add(max(start, min(end, ev["s"])))
        pts.add(max(start, min(end, ev["e"])))
    for bs, be in breaks:
        pts.add(max(start, min(end, bs)))
        pts.add(max(start, min(end, be)))
    pts = sorted(pts)
    comp = dict(planned_stop_s=0, unplanned_stop_s=0, minor_stop_s=0, gap_s=0, overlap_s=0,
                downtime_in_break_s=0, running_s=0)
    overlaps = defaultdict(int)
    break_hits = defaultdict(int)
    loss = defaultdict(int)
    for a, b in zip(pts, pts[1:]):
        d = b - a
        active = [ev for ev in events if ev["s"] <= a < ev["e"]]
        in_break = any(bs <= a < be for bs, be in breaks)
        if len(active) > 1:
            comp["overlap_s"] += d
            act = sorted(active, key=lambda ev: (ev["s"], ev["event_id"]))
            for other in act[1:]:
                overlaps[(other["event_id"], act[0]["event_id"])] += d
        if not active:
            if in_break:
                comp["planned_stop_s"] += d
            else:
                comp["gap_s"] += d
            continue
        ev = max(active, key=lambda x: (PRECEDENCE[x["state"]], x["s"], x["event_id"]))
        st = ev["state"]
        if in_break or st == "PLANNED_STOP":
            comp["planned_stop_s"] += d
            if in_break and st in ("STOPPED", "CHANGEOVER"):
                comp["downtime_in_break_s"] += d
                break_hits[ev["event_id"]] += d
        elif st == "RUNNING":
            comp["running_s"] += d
        elif st == "STOPPED" and ev["e"] - ev["s"] < threshold:
            comp["minor_stop_s"] += d
        else:
            comp["unplanned_stop_s"] += d
            loss[ev["reason"]] += d
    return comp, [(k[0], k[1], v) for k, v in overlaps.items()], dict(break_hits), dict(loss)


def valid_increments(readings, acknowledged_ids=frozenset()):
    """Walk one order's PLC readings in time order.

    readings: list of (count_id, ts, counter_value). Returns (accepted [(count_id, increment)],
    quarantined [(count_id, counter_value, running_max)]). A reading below the running maximum is
    quarantined unless a correction acknowledges it (then it is accepted as a counter reset).
    """
    accepted, quarantined = [], []
    last = 0
    for cid, _ts, counter in sorted(readings, key=lambda x: (x[1], x[0])):
        if counter < last:
            if cid in acknowledged_ids:
                accepted.append((cid, 0))
                last = counter
            else:
                quarantined.append((cid, counter, last))
            continue
        accepted.append((cid, counter - last))
        last = counter
    return accepted, quarantined


def ratio(n, d):
    return n / d if d else None


def oee_of(a, p, q):
    if a is None:
        return None
    if a == 0:
        return 0.0
    if p is None or q is None:
        return None
    return a * p * q


def calculate(base_dir: str) -> dict:
    inp = os.path.join(base_dir, "input")
    T = {n: read_table(inp, n) for n in (
        "plant", "line", "machine", "machine_product_standard", "downtime_reason", "shift", "shift_break",
        "production_order", "state_event", "downtime_annotation", "production_count", "quality_inspection")}
    plant_id = T["plant"][0]["plant_id"]
    machines = T["machine"]
    line_of = {m["machine_id"]: m["line_id"] for m in machines}
    shifts = T["shift"]
    shift_win = {s["shift_id"]: (parse_ts(s["start_ts"]), parse_ts(s["end_ts"])) for s in shifts}
    breaks = defaultdict(list)
    for b in T["shift_break"]:
        breaks[b["shift_id"]].append((parse_ts(b["start_ts"]), parse_ts(b["end_ts"])))
    std_ict = {s["standard_id"]: float(s["ideal_cycle_time_s"]) for s in T["machine_product_standard"]}
    orders = {o["order_id"]: o for o in T["production_order"]}

    exceptions = []

    def exc(issue, severity, table, rid, machine, shift, rule, treatment, impact=None, unit=None, related=None):
        exceptions.append(dict(issue_type=issue, severity=severity, record_table=table, record_id=rid,
                               related_record_ids=related, machine_id=machine, shift_id=shift,
                               detection_rule=rule, treatment=treatment, impact_value=impact, impact_unit=unit))

    ms_flags = defaultdict(set)

    # effective downtime reason = latest annotation, else the raw reason on the event
    latest_ann = {}
    for a in sorted(T["downtime_annotation"], key=lambda a: (parse_ts(a["annotated_ts"]), a["annotation_id"])):
        latest_ann[a["event_id"]] = a["reason_code"]

    # ---- time accounting --------------------------------------------------------------
    ev_by_ms = defaultdict(list)
    for ev in T["state_event"]:
        reason = latest_ann.get(ev["event_id"], ev["reason_code"] or None)
        ev_by_ms[(ev["machine_id"], ev["shift_id"])].append(dict(
            event_id=ev["event_id"], state=ev["state"], s=parse_ts(ev["start_ts"]), e=parse_ts(ev["end_ts"]),
            reason=reason))
        if (ev["state"] == "STOPPED" and reason == "DR-UNASSIGNED"
                and int(ev["duration_s"]) >= C.MICRO_STOP_THRESHOLD_S):
            exc("UNANNOTATED_DOWNTIME", "INFO", "state_event", ev["event_id"], ev["machine_id"], ev["shift_id"],
                "STOPPED >= micro-stop threshold without an annotation",
                "counted as availability loss under DR-UNASSIGNED; listed for operator follow-up",
                int(ev["duration_s"]), "seconds")

    time_comp, loss_by_ms = {}, {}
    for m in machines:
        mid = m["machine_id"]
        for s in shifts:
            sid = s["shift_id"]
            st, en = shift_win[sid]
            comp, overlaps, hits, loss = classify_machine_shift(ev_by_ms.get((mid, sid), []), breaks[sid], st, en)
            time_comp[(mid, sid)] = comp
            loss_by_ms[(mid, sid)] = loss
            for primary, other, secs in overlaps:
                ms_flags[(mid, sid)].add("OVERLAPPING_STATE")
                exc("OVERLAPPING_STATE", "ERROR", "state_event", primary, mid, sid,
                    "two state events of one machine cover the same instant",
                    "resolved by precedence PLANNED_STOP > STOPPED > CHANGEOVER > RUNNING; needs PLC review",
                    secs, "seconds", other)
            for eid, secs in sorted(hits.items()):
                ms_flags[(mid, sid)].add("DOWNTIME_OVERLAPS_BREAK")
                exc("DOWNTIME_OVERLAPS_BREAK", "WARNING", "state_event", eid, mid, sid,
                    "STOPPED/CHANGEOVER event intersects a planned break window",
                    "intersecting seconds counted as planned downtime (excluded from PPT)", secs, "seconds")
            if comp["gap_s"]:
                ms_flags[(mid, sid)].add("TIME_GAP")
                exc("TIME_GAP", "WARNING", "state_event", f"{mid}|{sid}", mid, sid,
                    "part of the shift is not covered by any state event",
                    "gap treated as unplanned stop", comp["gap_s"], "seconds")

    # ---- counts ----------------------------------------------------------------------
    readings_by_order = defaultdict(list)
    reading_shift = {}
    corrections = []
    for c in T["production_count"]:
        if c["record_type"] == "PLC_READING":
            readings_by_order[c["order_id"]].append((c["count_id"], parse_ts(c["record_ts"]), int(c["counter_value"])))
            reading_shift[c["count_id"]] = (c["machine_id"], c["shift_id"])
        else:
            corrections.append(c)
    acknowledged = {c["corrects_count_id"] for c in corrections if c["correction_reason"] == "COUNTER_RESET"}
    total_by_os = defaultdict(int)          # (order, machine, shift) -> units
    count_records_ms = defaultdict(int)
    for oid, rs in readings_by_order.items():
        accepted, quarantined = valid_increments(rs, acknowledged)
        for cid, inc in accepted:
            mid, sid = reading_shift[cid]
            total_by_os[(oid, mid, sid)] += inc
            count_records_ms[(mid, sid)] += 1
        for cid, counter, run_max in quarantined:
            mid, sid = reading_shift[cid]
            ms_flags[(mid, sid)].add("COUNT_DECREASE_NO_CORRECTION")
            count_records_ms[(mid, sid)] += 1
            exc("COUNT_DECREASE_NO_CORRECTION", "ERROR", "production_count", cid, mid, sid,
                "counter_value below running maximum and no MANUAL_CORRECTION references it",
                "reading quarantined (excluded from totals); original row kept",
                run_max - counter, "units")
    for c in corrections:
        mid, sid = reading_shift.get(c["corrects_count_id"], (c["machine_id"], c["shift_id"]))
        total_by_os[(c["order_id"], mid, sid)] += int(c["increment_qty"])
        count_records_ms[(mid, sid)] += 1

    # ---- ideal cycle time ---------------------------------------------------------------
    wrong_ict = {}
    for oid, o in orders.items():
        master = std_ict[o["standard_id"]]
        if abs(float(o["ideal_cycle_time_s"]) - master) > C.ICT_TOLERANCE_S:
            wrong_ict[oid] = master
            exc("WRONG_IDEAL_CYCLE_TIME", "WARNING", "production_order", oid, o["machine_id"], None,
                "|order.ideal_cycle_time_s - standard.ideal_cycle_time_s| > 0.05 s",
                f"master standard {o['standard_id']} ({master}s) used instead of {o['ideal_cycle_time_s']}s",
                float(o["ideal_cycle_time_s"]) - master, "seconds", o["standard_id"])

    # ---- quality ------------------------------------------------------------------------
    lot_total = defaultdict(int)
    for (oid, mid, sid), u in total_by_os.items():
        lot_total[(oid, sid)] += u
    scrap_ms, rework_ms = defaultdict(int), defaultdict(int)
    insp_ms = defaultdict(int)
    has_disp = set()
    for q in T["quality_inspection"]:
        mid, sid = q["machine_id"], q["shift_id"]
        insp_ms[(mid, sid)] += 1
        if q["inspection_type"] != "LOT_DISPOSITION":
            continue
        has_disp.add((q["order_id"], sid))
        total = lot_total.get((q["order_id"], sid), 0)
        scrap, rework = int(q["scrap_qty"]), int(q["rework_qty"])
        if scrap + rework > total:
            ms_flags[(mid, sid)].add("SCRAP_EXCEEDS_TOTAL")
            exc("SCRAP_EXCEEDS_TOTAL", "ERROR", "quality_inspection", q["inspection_id"], mid, sid,
                "scrap_qty + rework_qty > counted total for the order+shift lot",
                "disposition quarantined; quality uses remaining valid lots; needs quality engineer review",
                scrap + rework - total, "units", q["order_id"])
            continue
        if int(q["inspected_qty"]) != total:
            ms_flags[(mid, sid)].add("LOT_QTY_MISMATCH")
            exc("LOT_QTY_MISMATCH", "WARNING", "quality_inspection", q["inspection_id"], mid, sid,
                "inspected_qty differs from counted lot total", "counted total used", int(q["inspected_qty"]) - total,
                "units", q["order_id"])
        scrap_ms[(mid, sid)] += scrap
        rework_ms[(mid, sid)] += rework
    for (oid, mid, sid), u in sorted(total_by_os.items()):
        if u > 0 and (oid, sid) not in has_disp:
            ms_flags[(mid, sid)].add("MISSING_DISPOSITION")
            exc("MISSING_DISPOSITION", "WARNING", "production_order", oid, mid, sid,
                "lot produced but no LOT_DISPOSITION", "lot assumed all good (quality overstated)", u, "units")

    # ---- machine-shift aggregates -----------------------------------------------------------
    by_ms_orders = defaultdict(list)
    for (oid, mid, sid), u in total_by_os.items():
        by_ms_orders[(mid, sid)].append((oid, u))
    aggs = []
    sched = {s["shift_id"]: s["is_production_scheduled"] == "true" for s in shifts}
    for m in machines:
        mid = m["machine_id"]
        for s in shifts:
            sid = s["shift_id"]
            comp = time_comp[(mid, sid)]
            length = int(s["duration_s"])
            ppt = length - comp["planned_stop_s"]
            run = comp["running_s"] + comp["minor_stop_s"]
            total = sum(u for _, u in by_ms_orders[(mid, sid)])
            ideal = 0.0
            for oid, u in sorted(by_ms_orders[(mid, sid)]):
                ideal += u * std_ict[orders[oid]["standard_id"]]
                if oid in wrong_ict:
                    ms_flags[(mid, sid)].add("WRONG_IDEAL_CYCLE_TIME")
            scrap, rework = scrap_ms[(mid, sid)], rework_ms[(mid, sid)]
            good = total - scrap - rework
            a, p, q = ratio(run, ppt), ratio(ideal, run), ratio(good, total)
            if p is not None and p > 1.0 + 1e-9:
                ms_flags[(mid, sid)].add("PERFORMANCE_ABOVE_100")
                exc("PERFORMANCE_ABOVE_100", "WARNING", "oee_aggregate", f"{mid}|{sid}", mid, sid,
                    "performance > 100%", "kept as computed; check ideal cycle time / counts", p, "ratio")
            flags = ms_flags.get((mid, sid), set())
            status = "NOT_SCHEDULED" if not sched[sid] and ppt == 0 else ("EXCEPTION" if flags else "CLEAN")
            loss = loss_by_ms[(mid, sid)]
            top = max(sorted(loss), key=lambda k: loss[k]) if loss else None
            aggs.append(dict(
                aggregate_id=f"OEE-MS-{mid}-{sid}", aggregate_level="MACHINE_SHIFT", plant_id=plant_id,
                line_id=line_of[mid], machine_id=mid, shift_id=sid, shift_duration_s=length,
                planned_production_time_s=ppt, run_time_s=run, total_count=total, scrap_count=scrap,
                rework_count=rework, good_count=good, ideal_run_time_s=round(ideal, 3),
                availability=a, performance=p, quality=q, oee=oee_of(a, p, q), data_quality_status=status,
                exception_codes="|".join(sorted(flags)) or None, top_loss_reason_code=top,
                source_event_count=len(ev_by_ms.get((mid, sid), [])),
                source_count_record_count=count_records_ms[(mid, sid)],
                source_inspection_count=insp_ms[(mid, sid)], calc_version=C.CALC_VERSION, **comp))

    # ---- roll-ups (sum components, then ratio) ---------------------------------------------
    sum_fields = ["shift_duration_s", "planned_stop_s", "planned_production_time_s", "unplanned_stop_s",
                  "minor_stop_s", "gap_s", "overlap_s", "downtime_in_break_s", "running_s", "run_time_s",
                  "total_count", "scrap_count", "rework_count", "good_count", "ideal_run_time_s",
                  "source_event_count", "source_count_record_count", "source_inspection_count"]
    groups = defaultdict(list)
    for r in aggs:
        groups[("LINE_SHIFT", r["line_id"], r["shift_id"])].append(r)
        groups[("PLANT_SHIFT", plant_id, r["shift_id"])].append(r)
    rollups = []
    for (level, key, sid), rows in groups.items():
        agg = {f: sum(r[f] for r in rows) for f in sum_fields}
        agg["ideal_run_time_s"] = round(agg["ideal_run_time_s"], 3)
        a = ratio(agg["run_time_s"], agg["planned_production_time_s"])
        p = ratio(agg["ideal_run_time_s"], agg["run_time_s"])
        q = ratio(agg["good_count"], agg["total_count"])
        flags = sorted({c for r in rows if r["exception_codes"] for c in r["exception_codes"].split("|")})
        status = ("NOT_SCHEDULED" if all(r["data_quality_status"] == "NOT_SCHEDULED" for r in rows)
                  else "EXCEPTION" if flags else "CLEAN")
        loss = defaultdict(int)
        for r in rows:
            for k, v in loss_by_ms[(r["machine_id"], sid)].items():
                loss[k] += v
        rollups.append(dict(
            aggregate_id=f"OEE-{'LS' if level == 'LINE_SHIFT' else 'PS'}-{key}-{sid}", aggregate_level=level,
            plant_id=plant_id, line_id=key if level == "LINE_SHIFT" else None, machine_id=None, shift_id=sid,
            availability=a, performance=p, quality=q, oee=oee_of(a, p, q), data_quality_status=status,
            exception_codes="|".join(flags) or None,
            top_loss_reason_code=max(sorted(loss), key=lambda k: loss[k]) if loss else None,
            calc_version=C.CALC_VERSION, **agg))
    rollups.sort(key=lambda r: (r["aggregate_level"], r["shift_id"], r["aggregate_id"]))
    all_aggs = aggs + rollups

    exceptions.sort(key=lambda x: (x["issue_type"], x["record_id"], x["related_record_ids"] or ""))
    for n, x in enumerate(exceptions, 1):
        x["exception_id"] = ids.exception_id(n)
    out = os.path.join(base_dir, "derived")
    write_table(out, "oee_aggregate", all_aggs)
    write_table(out, "oee_exception", exceptions)
    by_type = defaultdict(int)
    for x in exceptions:
        by_type[x["issue_type"]] += 1
    return dict(aggregates=len(all_aggs), exceptions=dict(sorted(by_type.items())))
