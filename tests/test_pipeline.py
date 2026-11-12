"""End-to-end tests on a small dataset produced by the same generator as the full dataset."""
import os
import re
import shutil
import tempfile
import unittest
from collections import defaultdict

from oee import config as C
from oee.__main__ import run_pipeline
from oee.ids import PATTERNS, parse_ts
from oee.schema import BY_NAME, ISSUE_TYPES
from oee.tableio import read_table

SCALE = C.STARTER


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="oee-test-")
        cls.out = os.path.join(cls.tmp, "a")
        cls.result = run_pipeline(cls.out, SCALE, C.DEFAULT_SEED, formats=("json", "sql", "sqlite"), quiet=True)
        cls.inp = os.path.join(cls.out, "input")
        cls.der = os.path.join(cls.out, "derived")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def table(self, name):
        return read_table(os.path.join(self.out, BY_NAME[name].layer), name)

    # --- volume and identifiers -------------------------------------------------------
    def test_volume_targets_are_exact(self):
        rc = self.result["generate"]["row_counts"]
        self.assertEqual(rc["state_event"], SCALE.target_state_events)
        self.assertEqual(rc["production_count"] + rc["quality_inspection"], SCALE.target_count_inspection_records)
        self.assertEqual(rc["machine"], SCALE.machines)
        self.assertEqual(rc["product"], SCALE.products)
        self.assertEqual(rc["shift"], SCALE.days * 3)

    def test_id_conventions(self):
        checks = [("production_order", "order_id", r"^PO-2026-\d{6}$"),
                  ("shift", "shift_id", r"^SHIFT-\d{4}-\d{2}-\d{2}-[ABC]$"),
                  ("quality_inspection", "inspection_id", r"^QC-2026-\d{6}$")]
        for t, col, pat in checks:
            for r in self.table(t):
                self.assertRegex(r[col], pat)
        for e in self.table("state_event"):
            self.assertTrue(e["event_id"].startswith(f"EVT-{e['machine_id']}-"), e["event_id"])
        for c in self.table("production_count"):
            self.assertTrue(c["count_id"].startswith(f"CNT-{c['order_id']}-"), c["count_id"])

    # --- validation -------------------------------------------------------------------
    def test_all_validation_checks_pass(self):
        v = self.result["validate"]
        failed = [c for c in v["checks"] if c["status"] == "FAIL"]
        self.assertEqual(failed, [])
        categories = {c["category"] for c in v["checks"]}
        for cat in ("STRUCTURE", "FOREIGN_KEY", "TEMPORAL", "LIFECYCLE", "DUPLICATES", "RECONCILIATION"):
            self.assertIn(cat, categories)

    def test_sqlite_enforces_foreign_keys(self):
        self.assertEqual(self.result["export"]["sqlite"], {"foreign_key_violations": 0, "integrity": "ok"})

    # --- edge cases and ground truth ------------------------------------------------------
    def test_every_labelled_anomaly_detected_without_false_positives(self):
        det = self.result["evaluate"]["anomaly_detection"]
        for t in ISSUE_TYPES:
            self.assertEqual(det[t]["injected"], SCALE.anomalies_per_type, t)
            self.assertEqual(det[t]["precision"], 1.0, t)
            self.assertEqual(det[t]["recall"], 1.0, t)

    def test_ground_truth_is_not_in_inputs(self):
        self.assertEqual(sorted(os.listdir(self.inp)),
                         sorted(f"{t.name}.csv" for t in BY_NAME.values() if t.layer == "input"))
        for f in os.listdir(self.inp):
            with open(os.path.join(self.inp, f)) as fh:
                header = fh.readline()
            self.assertNotIn("issue_type", header)
            self.assertNotIn("true_", header)

    # --- acceptance criteria -----------------------------------------------------------------
    def test_oee_matches_independent_simulation_truth(self):
        o = self.result["evaluate"]["oee_accuracy"]
        self.assertEqual(o["unexplained_mismatch"], 0, o["unexplained_examples"])
        self.assertGreater(o["exact_match"], 0.95 * o["machine_shifts"])

    def test_oee_components_independently_recomputed(self):
        """Naive re-implementation from raw rows, for machine-shifts without overlaps."""
        events = defaultdict(list)
        for e in self.table("state_event"):
            events[(e["machine_id"], e["shift_id"])].append(e)
        breaks = defaultdict(list)
        for b in self.table("shift_break"):
            breaks[b["shift_id"]].append((parse_ts(b["start_ts"]), parse_ts(b["end_ts"])))
        checked = 0
        for a in self.table("oee_aggregate"):
            if a["aggregate_level"] != "MACHINE_SHIFT" or "OVERLAPPING_STATE" in (a["exception_codes"] or ""):
                continue
            run = ppt = 0
            for e in events[(a["machine_id"], a["shift_id"])]:
                s, t = parse_ts(e["start_ts"]), parse_ts(e["end_ts"])
                in_break = sum(max(0, min(t, be) - max(s, bs)) for bs, be in breaks[a["shift_id"]])
                if e["state"] == "PLANNED_STOP":
                    continue
                ppt += (t - s) - in_break
                if e["state"] == "RUNNING" or (e["state"] == "STOPPED" and t - s < C.MICRO_STOP_THRESHOLD_S):
                    run += (t - s) - in_break
            self.assertEqual(int(a["planned_production_time_s"]), ppt, a["aggregate_id"])
            self.assertEqual(int(a["run_time_s"]), run, a["aggregate_id"])
            if ppt:
                self.assertAlmostEqual(float(a["availability"]), run / ppt, places=6)
            checked += 1
        self.assertGreater(checked, 100)

    def test_planned_downtime_treatment_is_explicit(self):
        sched = {s["shift_id"]: s["is_production_scheduled"] == "true" for s in self.table("shift")}
        brk = defaultdict(int)
        for b in self.table("shift_break"):
            brk[b["shift_id"]] += int(b["duration_s"])
        for a in self.table("oee_aggregate"):
            if a["aggregate_level"] != "MACHINE_SHIFT":
                continue
            if not sched[a["shift_id"]]:
                self.assertEqual(a["data_quality_status"], "NOT_SCHEDULED")
                self.assertEqual(a["planned_production_time_s"], "0")
                self.assertEqual(a["oee"], "")
            else:   # breaks are always planned, whatever the machine reported during them
                self.assertGreaterEqual(int(a["planned_stop_s"]), brk[a["shift_id"]])

    def test_corrections_retain_original_events(self):
        counts = {c["count_id"]: c for c in self.table("production_count")}
        corrections = [c for c in counts.values() if c["record_type"] == "MANUAL_CORRECTION"]
        self.assertGreater(len(corrections), 0)
        for c in corrections:
            orig = counts[c["corrects_count_id"]]          # original still present, unchanged type
            self.assertEqual(orig["record_type"], "PLC_READING")
            self.assertLess(int(c["increment_qty"]), 0)
            self.assertGreaterEqual(parse_ts(c["record_ts"]), parse_ts(orig["record_ts"]))
        anns = {a["annotation_id"]: a for a in self.table("downtime_annotation")}
        for a in anns.values():
            if a["supersedes_annotation_id"]:
                self.assertIn(a["supersedes_annotation_id"], anns)   # superseded annotation kept

    def test_rollups_are_weighted_not_averaged(self):
        ms = defaultdict(lambda: [0, 0])
        for a in self.table("oee_aggregate"):
            if a["aggregate_level"] == "MACHINE_SHIFT":
                ms[a["shift_id"]][0] += int(a["run_time_s"])
                ms[a["shift_id"]][1] += int(a["planned_production_time_s"])
        for a in self.table("oee_aggregate"):
            if a["aggregate_level"] == "PLANT_SHIFT" and a["availability"]:
                run, ppt = ms[a["shift_id"]]
                self.assertAlmostEqual(float(a["availability"]), run / ppt, places=6)

    # --- reproducibility -----------------------------------------------------------------------
    def test_same_seed_reproduces_byte_identical_outputs(self):
        other = os.path.join(self.tmp, "b")
        m2 = run_pipeline(other, SCALE, C.DEFAULT_SEED, formats=("json", "sql"), quiet=True)["manifest"]
        m1 = {f["path"]: f["sha256"] for f in self.result["manifest"]["files"]}
        for f in m2["files"]:
            self.assertEqual(m1[f["path"]], f["sha256"], f["path"])

    def test_different_seed_changes_data(self):
        other = os.path.join(self.tmp, "c")
        m3 = run_pipeline(other, SCALE, C.DEFAULT_SEED + 1, formats=(), quiet=True)["manifest"]
        m1 = {f["path"]: f["sha256"] for f in self.result["manifest"]["files"]}
        f3 = {f["path"]: f["sha256"] for f in m3["files"]}
        self.assertNotEqual(m1["input/state_event.csv"], f3["input/state_event.csv"])


if __name__ == "__main__":
    unittest.main()
