"""Unit tests for the calculation rules on small hand-made cases (no generator involved)."""
import unittest

from oee.calculator import classify_machine_shift, oee_of, valid_increments


def ev(eid, state, s, e, reason=None):
    return dict(event_id=eid, state=state, s=s, e=e, reason=reason)


class TimeAccounting(unittest.TestCase):
    def test_clean_shift_reconciles(self):
        events = [ev("E1", "RUNNING", 0, 400), ev("E2", "PLANNED_STOP", 400, 500, "DR-BRK-TEA"),
                  ev("E3", "STOPPED", 500, 560, "DR-MICRO"),        # 60 s  -> minor stop
                  ev("E4", "RUNNING", 560, 800), ev("E5", "STOPPED", 800, 1000, "DR-MECH")]
        comp, overlaps, hits, loss = classify_machine_shift(events, [(400, 500)], 0, 1000)
        self.assertEqual(comp["planned_stop_s"], 100)
        self.assertEqual(comp["minor_stop_s"], 60)
        self.assertEqual(comp["unplanned_stop_s"], 200)
        self.assertEqual(comp["running_s"], 640)
        self.assertEqual(sum(comp[k] for k in ("planned_stop_s", "minor_stop_s", "unplanned_stop_s",
                                               "running_s", "gap_s")), 1000)
        self.assertEqual(overlaps, [])
        self.assertEqual(loss, {"DR-MECH": 200})

    def test_downtime_inside_break_is_planned(self):
        # machine reports a breakdown 300..450 but the break window is 400..500
        events = [ev("E1", "RUNNING", 0, 300), ev("E2", "STOPPED", 300, 450, "DR-MECH"),
                  ev("E3", "PLANNED_STOP", 450, 500), ev("E4", "RUNNING", 500, 1000)]
        comp, _, hits, _ = classify_machine_shift(events, [(400, 500)], 0, 1000)
        self.assertEqual(comp["planned_stop_s"], 100)      # the whole break window, not 50
        self.assertEqual(comp["unplanned_stop_s"], 100)    # only 300..400
        self.assertEqual(comp["downtime_in_break_s"], 50)
        self.assertEqual(hits, {"E2": 50})

    def test_overlap_resolved_by_precedence_and_reported(self):
        events = [ev("E1", "RUNNING", 0, 1000), ev("E2", "STOPPED", 200, 500, "DR-UNASSIGNED")]
        comp, overlaps, _, _ = classify_machine_shift(events, [], 0, 1000)
        self.assertEqual(comp["overlap_s"], 300)
        self.assertEqual(comp["unplanned_stop_s"], 300)    # STOPPED beats RUNNING
        self.assertEqual(comp["running_s"], 700)
        self.assertEqual(overlaps, [("E2", "E1", 300)])    # later-starting event is the primary

    def test_gap_is_unplanned_and_visible(self):
        comp, _, _, _ = classify_machine_shift([ev("E1", "RUNNING", 0, 600)], [], 0, 1000)
        self.assertEqual(comp["gap_s"], 400)
        self.assertEqual(comp["running_s"], 600)


class Counts(unittest.TestCase):
    def test_decrease_without_correction_is_quarantined(self):
        rs = [("C1", 10, 50), ("C2", 20, 30), ("C3", 30, 70)]
        accepted, quarantined = valid_increments(rs)
        self.assertEqual(accepted, [("C1", 50), ("C3", 20)])
        self.assertEqual(quarantined, [("C2", 30, 50)])
        self.assertEqual(sum(i for _, i in accepted), 70)   # = final counter, no double count

    def test_acknowledged_reset_is_accepted(self):
        accepted, quarantined = valid_increments([("C1", 10, 50), ("C2", 20, 0), ("C3", 30, 5)], {"C2"})
        self.assertEqual(quarantined, [])
        self.assertEqual(sum(i for _, i in accepted), 55)


class Formula(unittest.TestCase):
    def test_oee_edge_cases(self):
        self.assertIsNone(oee_of(None, None, None))   # no planned production time
        self.assertEqual(oee_of(0.0, None, None), 0.0)  # scheduled but never ran
        self.assertAlmostEqual(oee_of(0.9, 0.95, 0.99), 0.84645)


if __name__ == "__main__":
    unittest.main()
