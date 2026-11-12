"""Command line interface.

  python -m oee run --scale starter          # generate -> calculate -> validate -> evaluate -> export -> manifest
  python -m oee run --scale full             # 100k state events, 500k count + inspection records
  python -m oee repro --scale starter        # regenerate twice with the same seed and compare checksums
  python -m oee explain --out out/starter --machine MC-001 --shift SHIFT-2026-01-05-A
  python -m oee docs                         # regenerate docs/DATA_DICTIONARY.md, docs/ERD.md, docs/schema.sql
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

from . import config as C
from .calculator import calculate
from .evaluate import evaluate
from .exporter import export, manifest, write_docs
from .generator import generate
from .validator import validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scale(args) -> C.Scale:
    sc = C.SCALES[args.scale]
    if args.days:
        sc = C.make_scale(f"{sc.name}-{args.days}d", sc.lines, sc.machines_per_line, sc.products_per_line,
                          args.days, sc.anomalies_per_type)
    return sc


def run_pipeline(out: str, scale: C.Scale, seed: int, formats=("json", "sql", "sqlite"), quiet=False) -> dict:
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, flush=True))
    if os.path.exists(out):
        shutil.rmtree(out)
    t0 = time.time()
    g = generate(out, scale, seed)
    log(f"[generate] {scale.name} seed={seed}: state_event={g['row_counts']['state_event']:,} "
        f"production_count+quality_inspection={g['row_counts']['production_count'] + g['row_counts']['quality_inspection']:,} "
        f"({time.time() - t0:.1f}s)")
    t = time.time()
    c = calculate(out)
    log(f"[calculate] {c['aggregates']:,} OEE aggregates; exceptions {c['exceptions']} ({time.time() - t:.1f}s)")
    t = time.time()
    v = validate(out)
    log(f"[validate] {v['checks_passed']}/{v['checks_total']} checks passed ({time.time() - t:.1f}s)")
    t = time.time()
    e = evaluate(out)
    det = e["anomaly_detection"]
    log(f"[evaluate] detection recall " + ", ".join(f"{k}={d['recall']}" for k, d in det.items()))
    o = e["oee_accuracy"]
    log(f"[evaluate] OEE exact match {o['exact_match']}/{o['machine_shifts']}, "
        f"unresolvable-anomaly rows {o['differs_due_to_unresolvable_anomaly']}, unexplained {o['unexplained_mismatch']} "
        f"({time.time() - t:.1f}s)")
    t = time.time()
    x = export(out, formats)
    log(f"[export] {x} ({time.time() - t:.1f}s)")
    cmd = f"python -m oee run --scale {scale.name} --seed {seed} --out {os.path.relpath(out, ROOT)}"
    m = manifest(out, scale, seed, cmd)
    log(f"[manifest] {len(m['files'])} files, dataset checksum {m['dataset_checksum'][:16]}... "
        f"total {time.time() - t0:.1f}s")
    return dict(generate=g, calculate=c, validate=v, evaluate=e, export=x, manifest=m)


def cmd_repro(args):
    scale = _scale(args)
    base = os.path.join(args.out or os.path.join(ROOT, "out"), "_repro")
    runs = []
    for i, seed in enumerate((args.seed, args.seed, args.seed + 1), 1):
        d = os.path.join(base, f"run{i}")
        r = run_pipeline(d, scale, seed, formats=("json", "sql"), quiet=True)
        runs.append(r["manifest"])
        print(f"run{i} seed={seed}: dataset checksum {r['manifest']['dataset_checksum']}")
    a, b, c = runs
    fa = {f["path"]: f for f in a["files"]}
    fb = {f["path"]: f for f in b["files"]}
    diff = sorted(p for p in set(fa) | set(fb) if (fa.get(p) or {}).get("sha256") != (fb.get(p) or {}).get("sha256"))
    report = dict(scale=scale.as_dict(), seed=args.seed, files_compared=len(fa),
                  same_seed_identical=not diff and a["dataset_checksum"] == b["dataset_checksum"],
                  differing_files=diff,
                  row_counts={f["path"]: f["rows"] for f in a["files"] if f["rows"] is not None},
                  run1_checksum=a["dataset_checksum"], run2_checksum=b["dataset_checksum"],
                  different_seed_checksum=c["dataset_checksum"],
                  different_seed_differs=c["dataset_checksum"] != a["dataset_checksum"])
    path = os.path.join(base, "reproducibility.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"same seed identical: {report['same_seed_identical']} ({len(fa)} files); "
          f"different seed differs: {report['different_seed_differs']}; report: {path}")
    if not args.keep:
        for i in (1, 2, 3):
            shutil.rmtree(os.path.join(base, f"run{i}"), ignore_errors=True)
    return 0 if report["same_seed_identical"] and report["different_seed_differs"] else 1


def cmd_explain(args):
    """Trace one machine-shift back to its source records (for operators and engineers)."""
    from .tableio import read_table
    inp = os.path.join(args.out, "input")
    agg = [r for r in read_table(os.path.join(args.out, "derived"), "oee_aggregate")
           if r["machine_id"] == args.machine and r["shift_id"] == args.shift]
    if not agg:
        print("no such machine-shift")
        return 1
    a = agg[0]
    print(f"== {a['aggregate_id']}  status={a['data_quality_status']}  exceptions={a['exception_codes'] or '-'}")
    for k in ("shift_duration_s", "planned_stop_s", "planned_production_time_s", "unplanned_stop_s", "minor_stop_s",
              "gap_s", "overlap_s", "downtime_in_break_s", "running_s", "run_time_s", "total_count", "scrap_count",
              "rework_count", "good_count", "ideal_run_time_s", "availability", "performance", "quality", "oee"):
        print(f"   {k:28s} {a[k]}")
    print("-- breaks")
    for b in read_table(inp, "shift_break"):
        if b["shift_id"] == args.shift:
            print(f"   {b['break_id']} {b['break_type']} {b['start_ts'][11:19]}-{b['end_ts'][11:19]}")
    print("-- state events")
    for e in read_table(inp, "state_event"):
        if e["machine_id"] == args.machine and e["shift_id"] == args.shift:
            print(f"   {e['event_id']} {e['start_ts'][11:19]}-{e['end_ts'][11:19]} {e['state']:12s} "
                  f"{e['duration_s']:>6s}s {e['reason_code'] or '':14s} {e['order_id']}")
    print("-- count records")
    for c in read_table(inp, "production_count"):
        if c["machine_id"] == args.machine and c["shift_id"] == args.shift:
            print(f"   {c['count_id']} {c['record_ts'][11:19]} {c['record_type']:17s} counter={c['counter_value'] or '-':>6s} "
                  f"inc={c['increment_qty']:>5s} {c['corrects_count_id']}")
    print("-- lot dispositions")
    for q in read_table(inp, "quality_inspection"):
        if q["machine_id"] == args.machine and q["shift_id"] == args.shift and q["inspection_type"] == "LOT_DISPOSITION":
            print(f"   {q['inspection_id']} {q['order_id']} inspected={q['inspected_qty']} scrap={q['scrap_qty']} rework={q['rework_qty']}")
    print("-- exceptions")
    for x in read_table(os.path.join(args.out, "derived"), "oee_exception"):
        if x["machine_id"] == args.machine and x["shift_id"] in (args.shift, ""):
            print(f"   {x['exception_id']} {x['issue_type']} {x['record_id']}: {x['treatment']}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m oee", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "repro"):
        s = sub.add_parser(name)
        s.add_argument("--scale", choices=sorted(C.SCALES), default="starter")
        s.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
        s.add_argument("--days", type=int, help="override number of days (targets scale with it)")
        s.add_argument("--out", help="output directory (default out/<scale>)")
        if name == "run":
            s.add_argument("--formats", default="json,sql,sqlite", help="comma list of json,sql,sqlite")
        else:
            s.add_argument("--keep", action="store_true", help="keep the run directories")
    e = sub.add_parser("explain")
    e.add_argument("--out", default=os.path.join(ROOT, "out", "starter"))
    e.add_argument("--machine", required=True)
    e.add_argument("--shift", required=True)
    sub.add_parser("docs")
    args = p.parse_args(argv)

    if args.cmd == "run":
        scale = _scale(args)
        out = args.out or os.path.join(ROOT, "out", scale.name)
        r = run_pipeline(out, scale, args.seed, tuple(f for f in args.formats.split(",") if f))
        ok = r["validate"]["checks_failed"] == 0 and r["evaluate"]["oee_accuracy"]["unexplained_mismatch"] == 0
        return 0 if ok else 1
    if args.cmd == "repro":
        return cmd_repro(args)
    if args.cmd == "explain":
        return cmd_explain(args)
    if args.cmd == "docs":
        write_docs(os.path.join(ROOT, "docs"))
        print("docs written")
        return 0


if __name__ == "__main__":
    sys.exit(main())
