"""Evaluation: the only module that reads ground truth.

  1. anomaly detection: calculator exceptions vs injected anomalies (precision / recall per type)
  2. OEE accuracy: calculated machine-shift OEE vs the generator's own simulation
  3. annotation accuracy: operator / effective downtime reason vs true reason
  4. distribution profile of the generated data (is it realistic and varied?)
"""
from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict

from .schema import ISSUE_TYPES
from .tableio import read_table

# anomalies whose effect on OEE cannot be undone by a rule (the true value is unknowable from the data)
UNRESOLVABLE = {"OVERLAPPING_STATE", "SCRAP_EXCEEDS_TOTAL"}


def _pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 4)


def _profile(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return dict(n=len(vals), mean=round(statistics.fmean(vals), 4), p10=_pct(vals, 0.1), p50=_pct(vals, 0.5),
                p90=_pct(vals, 0.9), min=round(min(vals), 4), max=round(max(vals), 4))


def evaluate(base_dir: str) -> dict:
    gt = read_table(os.path.join(base_dir, "ground_truth"), "ground_truth_anomaly")
    truth = read_table(os.path.join(base_dir, "ground_truth"), "ground_truth_oee")
    true_reason = {r["event_id"]: r["true_reason_code"]
                   for r in read_table(os.path.join(base_dir, "ground_truth"), "ground_truth_downtime_reason")}
    exc = read_table(os.path.join(base_dir, "derived"), "oee_exception")
    aggs = read_table(os.path.join(base_dir, "derived"), "oee_aggregate")
    inp = os.path.join(base_dir, "input")

    # 1. detection
    detection = {}
    for t in ISSUE_TYPES:
        expected = {g["record_id"] for g in gt if g["issue_type"] == t}
        found = {x["record_id"] for x in exc if x["issue_type"] == t}
        tp = len(expected & found)
        detection[t] = dict(injected=len(expected), detected=len(found), true_positive=tp,
                            false_positive=len(found - expected), false_negative=len(expected - found),
                            precision=round(tp / len(found), 4) if found else None,
                            recall=round(tp / len(expected), 4) if expected else None,
                            missed=sorted(expected - found)[:10], unexpected=sorted(found - expected)[:10])

    # 2. OEE accuracy vs simulation truth
    ms = {(r["machine_id"], r["shift_id"]): r for r in aggs if r["aggregate_level"] == "MACHINE_SHIFT"}
    unresolvable_ms = {(g["machine_id"], g["shift_id"]) for g in gt if g["issue_type"] in UNRESOLVABLE}
    fields = ["planned_production_time_s", "run_time_s", "total_count", "good_count", "ideal_run_time_s",
              "availability", "performance", "quality", "oee"]
    exact, mismatched, explained, max_err = 0, [], 0, 0.0
    for t in truth:
        r = ms[(t["machine_id"], t["shift_id"])]
        diffs = []
        for f in fields:
            a, b = t[f], r[f]
            if (a == "") != (b == ""):
                diffs.append(f)
            elif a != "":
                err = abs(float(a) - float(b))
                if err > 1e-6 * max(1.0, abs(float(a))):
                    diffs.append(f)
                if f == "oee":
                    max_err = max(max_err, err) if (t["machine_id"], t["shift_id"]) not in unresolvable_ms else max_err
        if not diffs:
            exact += 1
        elif (t["machine_id"], t["shift_id"]) in unresolvable_ms:
            explained += 1
        else:
            mismatched.append(f"{t['machine_id']}|{t['shift_id']}: {','.join(diffs)}")
    oee_accuracy = dict(machine_shifts=len(truth), exact_match=exact,
                        differs_due_to_unresolvable_anomaly=explained, unexplained_mismatch=len(mismatched),
                        unexplained_examples=mismatched[:10], max_abs_oee_error_on_resolvable_rows=max_err,
                        note="Overlapping states and impossible scrap make the true value unknowable from the data; "
                             "those rows are flagged EXCEPTION and expected to differ.")

    # 3. annotations
    anns = read_table(inp, "downtime_annotation")
    first, latest = {}, {}
    for a in sorted(anns, key=lambda a: (a["annotated_ts"], a["annotation_id"])):
        first.setdefault(a["event_id"], a["reason_code"])
        latest[a["event_id"]] = a["reason_code"]
    n = len(true_reason)
    annotation = dict(
        stops_requiring_reason=n, annotated=len(latest), unannotated=n - len(latest),
        operator_first_annotation_accuracy=round(sum(first[e] == true_reason[e] for e in first) / len(first), 4) if first else None,
        effective_reason_accuracy=round(sum(latest[e] == true_reason[e] for e in latest) / len(latest), 4) if latest else None,
        re_annotated_by_engineer=sum(1 for a in anns if a["supersedes_annotation_id"]))

    # 4. distributions
    scheduled = [r for r in ms.values() if r["data_quality_status"] != "NOT_SCHEDULED"]
    num = lambda r, k: float(r[k]) if r[k] != "" else None
    dist = {k: _profile([num(r, k) for r in scheduled]) for k in ("availability", "performance", "quality", "oee")}
    by_line = defaultdict(list)
    by_code = defaultdict(list)
    for r in aggs:
        if r["aggregate_level"] == "LINE_SHIFT" and r["oee"] != "":
            by_line[r["line_id"]].append(float(r["oee"]))
        if r["aggregate_level"] == "PLANT_SHIFT" and r["oee"] != "":
            by_code[r["shift_id"][-1]].append(float(r["oee"]))
    events = read_table(inp, "state_event")
    state_secs = Counter()
    for e in events:
        state_secs[e["state"]] += int(e["duration_s"])
    orders = read_table(inp, "production_order")
    insp = read_table(inp, "quality_inspection")
    counts = read_table(inp, "production_count")
    loss = Counter()
    for r in scheduled:
        if r["top_loss_reason_code"]:
            loss[r["top_loss_reason_code"]] += 1
    profile = dict(
        machine_shift_kpis=dist,
        line_oee_mean={k: round(statistics.fmean(v), 4) for k, v in sorted(by_line.items())},
        plant_oee_mean_by_shift_code={k: round(statistics.fmean(v), 4) for k, v in sorted(by_code.items())},
        state_time_share={k: round(v / sum(state_secs.values()), 4) for k, v in sorted(state_secs.items())},
        events_by_state=dict(sorted(Counter(e["state"] for e in events).items())),
        micro_stops=sum(1 for e in events if e["state"] == "STOPPED" and int(e["duration_s"]) < 120),
        order_status=dict(sorted(Counter(o["current_status"] for o in orders).items())),
        inspections_by_type=dict(sorted(Counter(i["inspection_type"] for i in insp).items())),
        count_records_by_type=dict(sorted(Counter(c["record_type"] for c in counts).items())),
        top_loss_reason_by_machine_shift=dict(loss.most_common()),
        scheduled_machine_shifts=len(scheduled),
        clean_machine_shifts=sum(1 for r in scheduled if r["data_quality_status"] == "CLEAN"))

    result = dict(anomaly_detection=detection, oee_accuracy=oee_accuracy, annotation_accuracy=annotation,
                  data_profile=profile)
    out = os.path.join(base_dir, "reports")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "evaluation.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    with open(os.path.join(out, "evaluation.md"), "w") as fh:
        fh.write("# Evaluation against ground truth\n\n## Anomaly detection\n\n"
                 "| Issue type | Injected | Detected | TP | FP | FN | Precision | Recall |\n|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for t, v in detection.items():
            fh.write(f"| {t} | {v['injected']} | {v['detected']} | {v['true_positive']} | {v['false_positive']} | "
                     f"{v['false_negative']} | {v['precision']} | {v['recall']} |\n")
        o = oee_accuracy
        fh.write(f"\n## OEE vs simulation truth\n\n- machine-shifts compared: {o['machine_shifts']}\n"
                 f"- exact match (all 9 components): {o['exact_match']}\n"
                 f"- differ because of an unresolvable labelled anomaly: {o['differs_due_to_unresolvable_anomaly']}\n"
                 f"- unexplained mismatches: {o['unexplained_mismatch']}\n\n")
        fh.write("## Downtime annotation\n\n" + "\n".join(f"- {k}: {v}" for k, v in annotation.items()) + "\n\n")
        fh.write("## Data profile (scheduled machine-shifts)\n\n| KPI | mean | p10 | p50 | p90 |\n|---|---:|---:|---:|---:|\n")
        for k, v in dist.items():
            if v:
                fh.write(f"| {k} | {v['mean']} | {v['p10']} | {v['p50']} | {v['p90']} |\n")
        fh.write("\nOEE mean by line: " + json.dumps(profile["line_oee_mean"]) + "\n\n")
        fh.write("Plant OEE mean by shift code: " + json.dumps(profile["plant_oee_mean_by_shift_code"]) + "\n\n")
        fh.write("Order status: " + json.dumps(profile["order_status"]) + "\n")
    return result
