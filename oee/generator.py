"""Deterministic synthetic data generator for the OEE workflow.

Order of work (each step only uses records created by earlier steps, so every child row
has a valid parent and every derived value comes from source records):

  1. master data: plant, lines, machines, products, versioned ideal cycle times, reasons,
     shift calendar and planned breaks
  2. per machine, a time-ordered simulation of orders, changeovers, runs and stops
  3. labelled anomaly "downtime overlaps planned break" (changes the real timeline)
  4. micro-stops, calibrated so the state-event total hits the configured target exactly
  5. production from run time / actual cycle time; inspections; PLC counter readings
     (calibrated so counts + inspections hit the configured target exactly); sensor
     double-counts with manual corrections that point at the original reading
  6. remaining labelled anomalies (overlap, counter decrease, scrap > total, wrong ICT)
  7. downtime annotations, order lifecycle history, generator-side ground truth
  8. deterministic IDs, then CSV output (inputs and ground truth in separate folders)

All randomness comes from random.Random seeded with "<seed>|<purpose>|<key>", so each
machine/purpose has an independent, reproducible stream.
"""
from __future__ import annotations

import bisect
import math
import os
import random
from collections import defaultdict
from datetime import timedelta

from . import config as C
from . import ids
from .tableio import write_table

FAMILIES = [
    ("Gearbox housings", "CNC_MILL", (60, 110)),
    ("Brake discs", "CNC_LATHE", (35, 70)),
    ("Polymer clips", "INJECTION_MOLDER", (18, 40)),
    ("Mounting brackets", "STAMPING_PRESS", (4, 10)),
    ("Pump shafts", "GRINDER", (40, 80)),
]
# reason code, weight, median duration (minutes)
UNPLANNED = [("DR-MECH", 0.45, 18), ("DR-ELEC", 0.20, 12), ("DR-MAT", 0.20, 10),
             ("DR-QH", 0.08, 20), ("DR-OPR", 0.07, 8)]
UNPLANNED_CODES = [u[0] for u in UNPLANNED]
REASONS = [
    # code, description, category, oee bucket, planned, requires annotation
    ("DR-BRK-TEA", "Scheduled tea break", "PLANNED_STOP", "NONE", True, False),
    ("DR-BRK-MEAL", "Scheduled meal break", "PLANNED_STOP", "NONE", True, False),
    ("DR-PM", "Preventive maintenance (planned)", "PLANNED_STOP", "NONE", True, False),
    ("DR-NOSCHED", "No production scheduled (plant closed)", "PLANNED_STOP", "NONE", True, False),
    ("DR-CO", "Changeover / setup between orders", "SETUP", "AVAILABILITY", False, False),
    ("DR-MECH", "Mechanical breakdown", "UNPLANNED_STOP", "AVAILABILITY", False, True),
    ("DR-ELEC", "Electrical / control fault", "UNPLANNED_STOP", "AVAILABILITY", False, True),
    ("DR-MAT", "Material shortage / starved", "UNPLANNED_STOP", "AVAILABILITY", False, True),
    ("DR-QH", "Quality hold", "UNPLANNED_STOP", "AVAILABILITY", False, True),
    ("DR-OPR", "No operator available", "UNPLANNED_STOP", "AVAILABILITY", False, True),
    ("DR-MICRO", "Minor stop (< threshold), auto-classified", "MINOR_STOP", "PERFORMANCE", False, False),
    ("DR-UNASSIGNED", "Stop not yet annotated", "UNKNOWN", "AVAILABILITY", False, True),
]
SHIFT_SPEED = {"A": 1.00, "B": 1.01, "C": 1.04}    # night shift runs a bit slower
SHIFT_QUALITY = {"A": 1.0, "B": 1.1, "C": 1.3}      # ...and makes a bit more scrap
STANDARD_EPOCH = ids.day_offset(C.HORIZON_START.replace(year=C.HORIZON_START.year - 1, month=10))


def binom(r: random.Random, n: int, p: float) -> int:
    """Binomial draw that is fast for large n (normal approximation) and exact for small n."""
    if n <= 0 or p <= 0:
        return 0
    if n < 60:
        return sum(1 for _ in range(n) if r.random() < p)
    x = round(r.gauss(n * p, math.sqrt(n * p * (1 - p))))
    return max(0, min(n, x))


class Generator:
    def __init__(self, scale: C.Scale, seed: int = C.DEFAULT_SEED):
        self.scale = scale
        self.seed = seed
        self.gt: list[dict] = []
        self.used_machine_shifts: set = set()
        self.stats: dict = {}

    def rng(self, *parts) -> random.Random:
        return random.Random(f"{self.seed}|" + "|".join(str(p) for p in parts))

    # ------------------------------------------------------------------ 1. masters
    def build_masters(self):
        sc, r = self.scale, self.rng("masters")
        self.plant = dict(plant_id=ids.plant_id(1), plant_name="Pune Components Plant",
                          timezone=C.PLANT_TIMEZONE, country_code="IN", status="ACTIVE",
                          effective_from="2020-04-01")
        self.lines, self.machines, self.products, self.standards = [], [], [], []
        self.std_by_mp = {}
        pn = mn = 0
        mid_horizon = ids.day_offset(C.HORIZON_START + timedelta(days=sc.days // 2))
        for li in range(sc.lines):
            fam, mtype, (lo, hi) = FAMILIES[li % len(FAMILIES)]
            lid = ids.line_id(li + 1)
            self.lines.append(dict(line_id=lid, plant_id=self.plant["plant_id"],
                                   line_name=f"Line {li + 1} - {fam}", product_family=fam,
                                   status="ACTIVE", effective_from="2021-01-01"))
            prods = []
            for k in range(sc.products_per_line):
                pn += 1
                p = dict(product_id=ids.product_id(pn), product_name=f"{fam[:-1]} type {chr(65 + k)}",
                         product_family=fam, unit_of_measure="EA", status="ACTIVE",
                         effective_from="2022-01-01", _base=round(r.uniform(lo, hi), 1))
                prods.append(p)
                self.products.append(p)
            for j in range(sc.machines_per_line):
                mn += 1
                m = dict(machine_id=ids.machine_id(mn), line_id=lid,
                         machine_name=f"{mtype.replace('_', ' ').title()} {li + 1}.{j + 1}",
                         machine_type=mtype, position_in_line=j + 1,
                         commissioned_date=f"{2022 + r.randint(0, 2)}-{r.randint(1, 12):02d}-01",
                         status="ACTIVE", effective_from="2025-10-01",
                         _idx=mn - 1, _products=prods,
                         _mtbs=r.uniform(110, 260) * 60,          # mean run time between stops
                         _speed=r.uniform(1.0, 1.06),             # machine-specific speed loss
                         _scrap=r.uniform(0.004, 0.025), _rework=r.uniform(0.002, 0.012))
                self.machines.append(m)
                for p in prods:
                    ict = round(p["_base"] * r.uniform(0.9, 1.12), 1)
                    versions = [dict(machine_id=m["machine_id"], product_id=p["product_id"], version=1,
                                     ideal_cycle_time_s=ict, _from=STANDARD_EPOCH, _to=None,
                                     approved_by_role="PRODUCTION_PLANNER")]
                    if r.random() < 0.25:  # process improvement mid-horizon -> new version
                        versions[0]["_to"] = mid_horizon
                        versions.append(dict(machine_id=m["machine_id"], product_id=p["product_id"], version=2,
                                             ideal_cycle_time_s=round(ict * r.uniform(0.9, 0.96), 1),
                                             _from=mid_horizon, _to=None,
                                             approved_by_role="MAINTENANCE_ENGINEER"))
                    for v in versions:
                        v["standard_id"] = ids.standard_id(m["machine_id"], p["product_id"], v["version"])
                        self.standards.append(v)
                    self.std_by_mp[(m["machine_id"], p["product_id"])] = versions

        self.shifts = []
        for d in range(sc.days):
            day = C.HORIZON_START + timedelta(days=d)
            for code, hour in C.SHIFT_STARTS.items():
                s = d * 86400 + hour * 3600
                note = None
                if day in C.HOLIDAYS:
                    note = "HOLIDAY"
                elif code == "C" and day.weekday() in C.UNSCHEDULED_C_WEEKDAYS:
                    note = "WEEKEND_NIGHT"
                sid = ids.shift_id(day, code)
                breaks = [] if note else [(typ, s + off * 60, s + (off + dur) * 60)
                                          for typ, off, dur in C.SHIFT_BREAKS]
                self.shifts.append(dict(idx=len(self.shifts), shift_id=sid, date=day, code=code, s=s,
                                        e=s + C.SHIFT_LENGTH_S, sched=note is None, note=note, breaks=breaks))
        self.horizon_end = self.shifts[-1]["e"]

    def std_at(self, m, p, ts):
        for v in self.std_by_mp[(m["machine_id"], p["product_id"])]:
            if v["_from"] <= ts and (v["_to"] is None or ts < v["_to"]):
                return v
        raise ValueError("no standard effective")

    # ------------------------------------------------------------------ 2. simulation
    def new_order(self, r, m, t, prev_product):
        choices = [p for p in m["_products"] if p is not prev_product] or m["_products"]
        p = r.choice(choices)
        released = t - r.randint(4 * 3600, 36 * 3600)
        created = released - r.randint(86400, 3 * 86400)
        std = self.std_at(m, p, released)
        ict = std["ideal_cycle_time_s"]
        act_ct = ict * r.uniform(1.03, 1.15) * m["_speed"]
        planned_qty = max(50, int(round(r.uniform(3, 16) * 3600 / (ict * 1.1) / 50)) * 50)
        pstart = t + r.randint(-120, 120) * 60
        return dict(m=m, p=p, std=std, ict=ict, snapshot_ict=ict, act_ct=act_ct, planned_qty=planned_qty,
                    run_left=int(planned_qty * act_ct * r.uniform(0.95, 1.07)), co_s=r.randint(15, 60) * 60,
                    created=created, released=released, pstart=pstart,
                    pend=pstart + int(planned_qty * ict / 0.85), start=None, end=None,
                    cancelled_ts=None, cum=0.0, readings=[])

    def cancelled_order(self, r, m, t):
        o = self.new_order(r, m, t + r.randint(2, 48) * 3600, None)
        o["cancelled_ts"] = t - r.randint(1, 10) * 3600
        o["created"] = min(o["created"], o["cancelled_ts"] - 3 * 86400)
        if r.random() < 0.5 or o["released"] >= o["cancelled_ts"]:
            o["released"] = None
        o["run_left"] = 0
        return o

    def draw_stop(self, r):
        x, acc = r.random(), 0.0
        for code, w, med in UNPLANNED:
            acc += w
            if x <= acc:
                break
        dur = int(med * 60 * math.exp(r.gauss(0, 0.6)))
        return code, max(180, min(3 * 3600, dur))

    def simulate_machine(self, m):
        r = self.rng("sim", m["machine_id"])
        segs, orders = [], []
        st = dict(cur=None, co_left=0, first=True, next_stop=None, prev=None)

        def add(s, e, state, raw, order, sh, true_reason=None):
            if e > s:
                segs.append(dict(s=s, e=e, st=state, rs=raw, tr=true_reason or raw, o=order, sh=sh,
                                 spur=False, gt=None, m=m))

        def window(a, b, sh):
            t = a
            while t < b:
                if st["cur"] is None:
                    if r.random() < 0.03:
                        orders.append(self.cancelled_order(r, m, t))
                    o = self.new_order(r, m, t, st["prev"])
                    o["start"] = t
                    orders.append(o)
                    st.update(cur=o, prev=o["p"], co_left=0 if st["first"] else o["co_s"], first=False)
                o = st["cur"]
                if st["co_left"] > 0:
                    d = min(st["co_left"], b - t)
                    add(t, t + d, "CHANGEOVER", "DR-CO", o, sh)
                    st["co_left"] -= d
                    t += d
                    continue
                if st["next_stop"] is None:
                    st["next_stop"] = max(60, int(r.expovariate(1 / m["_mtbs"])))
                d = min(max(st["next_stop"], 0), o["run_left"], b - t)
                if d > 0:
                    add(t, t + d, "RUNNING", None, o, sh)
                    t += d
                    o["run_left"] -= d
                    st["next_stop"] -= d
                if o["run_left"] <= 0:
                    o["end"] = t
                    st["cur"] = None
                    continue
                if st["next_stop"] <= 0 and t < b:
                    code, dur = self.draw_stop(r)
                    dur = min(dur, b - t)
                    add(t, t + dur, "STOPPED", "DR-UNASSIGNED", o, sh, code)
                    t += dur
                    st["next_stop"] = None

        for sh in self.shifts:
            if not sh["sched"]:
                add(sh["s"], sh["e"], "PLANNED_STOP", "DR-NOSCHED", None, sh)
                continue
            blocked = [(bs, be, f"DR-BRK-{typ}") for typ, bs, be in sh["breaks"]]
            if r.random() < 0.02:
                blocked.insert(0, (sh["s"], min(sh["s"] + r.randint(60, 150) * 60, blocked[0][0]), "DR-PM"))
            t = sh["s"]
            for bs, be, code in blocked:
                if t < bs:
                    window(t, bs, sh)
                add(bs, be, "PLANNED_STOP", code, None, sh)
                t = be
            window(t, sh["e"], sh)
        # one released-but-not-started order per machine at the end of the horizon
        la = self.new_order(r, m, self.horizon_end + r.randint(1, 8) * 3600, st["prev"])
        la["run_left"] = 0
        orders.append(la)
        m["_segs"], m["_orders"] = segs, orders

    # ------------------------------------------------------------------ helpers
    def _ms_key(self, seg_or_m, sh):
        m = seg_or_m["m"] if "m" in seg_or_m else seg_or_m
        return (m["machine_id"], sh["shift_id"])

    def _pick(self, r, cands, n, key):
        """Pick up to n candidates, at most one anomaly per machine-shift."""
        idx = list(range(len(cands)))
        r.shuffle(idx)
        out = []
        for i in idx:
            k = key(cands[i])
            if k is not None and k in self.used_machine_shifts:
                continue
            if k is not None:
                self.used_machine_shifts.add(k)
            out.append(cands[i])
            if len(out) == n:
                break
        if len(out) < n:
            raise ValueError("not enough anomaly candidates; increase scale")
        return out

    def add_gt(self, issue, table, ref, machine_id, shift_id, injection, orig, new, detect, treat):
        self.gt.append(dict(issue_type=issue, record_table=table, _ref=ref, machine_id=machine_id,
                            shift_id=shift_id, injection=injection, original_value=orig,
                            injected_value=new, expected_detection=detect, expected_treatment=treat))

    # ------------------------------------------------------------------ 3. break overlap
    def inject_break_overlap(self, n):
        r = self.rng("anomaly", "break")
        cands = []
        for m in self.machines:
            segs = m["_segs"]
            for i in range(1, len(segs)):
                a, b = segs[i - 1], segs[i]
                if (b["st"] == "PLANNED_STOP" and b["rs"].startswith("DR-BRK") and a["st"] == "RUNNING"
                        and a["e"] - a["s"] >= 1800 and a["sh"] is b["sh"] and a["e"] == b["s"]):
                    cands.append((m, a, b))
        for m, a, b in self._pick(r, cands, n, lambda c: self._ms_key(c[0], c[1]["sh"])):
            x = r.randint(5, 15) * 60
            y = r.randint(3, (b["e"] - b["s"]) // 60 - 2) * 60
            stop = dict(s=a["e"] - x, e=b["s"] + y, st="STOPPED", rs="DR-UNASSIGNED", tr="DR-MECH", o=a["o"],
                        sh=a["sh"], spur=False, gt=None, m=m)
            a["e"] -= x
            b["s"] += y
            m["_segs"].insert(m["_segs"].index(b), stop)
            stop["gt"] = True
            self.add_gt("DOWNTIME_OVERLAPS_BREAK", "state_event", stop, m["machine_id"], a["sh"]["shift_id"],
                        f"unplanned stop extended {y // 60} min into the planned break",
                        None, f"{y}s inside break",
                        "STOPPED event intersects a shift_break window",
                        "intersecting seconds reclassified as planned downtime; rest stays availability loss")

    # ------------------------------------------------------------------ 4. micro stops
    def fill_micro_stops(self, reserved):
        total = sum(len(m["_segs"]) for m in self.machines)
        need = self.scale.target_state_events - reserved - total
        if need < 0:
            raise ValueError(f"structural events ({total}) exceed target; lower stop frequency")
        r = self.rng("micro")
        runs = [s for m in self.machines for s in m["_segs"]
                if s["st"] == "RUNNING" and s["e"] - s["s"] >= 300 and not s["gt"]]
        cum, w = [], 0
        for s in runs:
            w += s["e"] - s["s"]
            cum.append(w)
        counts = [0] * len(runs)
        for _ in range(need // 2):
            counts[min(bisect.bisect_right(cum, r.random() * w), len(runs) - 1)] += 1
        cap = [(s["e"] - s["s"]) // 240 for s in runs]
        overflow = 0
        for i in range(len(runs)):
            if counts[i] > cap[i]:
                overflow += counts[i] - cap[i]
                counts[i] = cap[i]
        for i in sorted(range(len(runs)), key=lambda i: (counts[i] - cap[i], i)):
            if overflow == 0:
                break
            add = min(overflow, cap[i] - counts[i])
            counts[i] += add
            overflow -= add
        if overflow:
            raise ValueError("not enough running time for micro-stops")
        tail = None
        if need % 2:
            tail = next(i for i in range(len(runs)) if counts[i] == 0)
        plan = {id(runs[i]): (counts[i], i == tail) for i in range(len(runs)) if counts[i] or i == tail}
        n_micro = 0
        for m in self.machines:
            out = []
            for s in m["_segs"]:
                if id(s) not in plan:
                    out.append(s)
                    continue
                k, is_tail = plan[id(s)]
                pieces = self._split(r, s, k, is_tail)
                n_micro += sum(1 for p in pieces if p["st"] == "STOPPED")
                out.extend(pieces)
            m["_segs"] = out
        self.stats["micro_stops"] = n_micro
        assert sum(len(m["_segs"]) for m in self.machines) + reserved == self.scale.target_state_events

    def _split(self, r, s, k, tail):
        def piece(a, b, state):
            raw = "DR-MICRO" if state == "STOPPED" else None
            return dict(s=a, e=b, st=state, rs=raw, tr=raw, o=s["o"], sh=s["sh"], spur=False, gt=None, m=s["m"])
        if tail:
            d = r.randint(20, 110)
            return [piece(s["s"], s["e"] - d, "RUNNING"), piece(s["e"] - d, s["e"], "STOPPED")]
        durs = [r.randint(20, 110) for _ in range(k)]
        free = (s["e"] - s["s"]) - sum(durs)
        spare = free - 30 * (k + 1)
        wts = [r.random() + 1e-9 for _ in range(k + 1)]
        runs = [30 + int(spare * x / sum(wts)) for x in wts]
        runs[-1] += free - sum(runs)
        out, t = [], s["s"]
        for i in range(k + 1):
            out.append(piece(t, t + runs[i], "RUNNING"))
            t += runs[i]
            if i < k:
                out.append(piece(t, t + durs[i], "STOPPED"))
                t += durs[i]
        assert t == s["e"]
        return out

    # ------------------------------------------------------------------ 5. production & quality
    def compute_production(self):
        for m in self.machines:
            for s in m["_segs"]:
                if s["st"] == "RUNNING":
                    o = s["o"]
                    s["rate"] = 1.0 / (o["act_ct"] * SHIFT_SPEED[s["sh"]["code"]])
                    s["c0"] = o["cum"]
                    o["cum"] = s["c0"] + (s["e"] - s["s"]) * s["rate"]
                    s["c1"] = o["cum"]
                    s["units"] = math.floor(s["c1"]) - math.floor(s["c0"])

    def build_inspections(self):
        self.inspections = []
        for m in self.machines:
            r = self.rng("qc", m["machine_id"])
            acc, nxt = 0, r.randint(3000, 4200)
            lots = {}
            for s in m["_segs"]:
                if s["st"] != "RUNNING":
                    continue
                dur = s["e"] - s["s"]
                while acc + dur >= nxt:
                    o, sh = s["o"], s["sh"]
                    n = 10 if o["ict"] < 30 else 5
                    p = (m["_scrap"] + m["_rework"]) * SHIFT_QUALITY[sh["code"]]
                    defects = binom(r, n, p)
                    self.inspections.append(dict(
                        inspection_type="SAMPLE", o=o, m=m, sh=sh, ts=s["s"] + (nxt - acc), sample_size=n,
                        defects_found=defects, result="PASS" if defects == 0 else "FAIL",
                        inspector_role="QUALITY_ENGINEER" if r.random() < 0.3 else "PLANT_OPERATOR"))
                    nxt += r.randint(3000, 4200)
                acc += dur
                if s["units"]:
                    key = (id(s["o"]), s["sh"]["idx"])
                    if key not in lots:
                        lots[key] = dict(o=s["o"], sh=s["sh"], units=0)
                    lots[key]["units"] += s["units"]
            for lot in lots.values():
                q = SHIFT_QUALITY[lot["sh"]["code"]]
                scrap = binom(r, lot["units"], m["_scrap"] * q)
                rework = min(binom(r, lot["units"], m["_rework"] * q), lot["units"] - scrap)
                self.inspections.append(dict(
                    inspection_type="LOT_DISPOSITION", o=lot["o"], m=m, sh=lot["sh"],
                    ts=lot["sh"]["e"] + r.randint(5, 45) * 60, inspected_qty=lot["units"],
                    scrap_qty=scrap, rework_qty=rework, true_scrap=scrap, result="DISPOSITIONED",
                    inspector_role="QUALITY_ENGINEER"))

    def build_readings(self, reserved):
        n_corr = round(self.scale.target_count_inspection_records * C.CORRECTION_RATE)
        budget = self.scale.target_count_inspection_records - len(self.inspections) - n_corr - reserved
        producing = [s for m in self.machines for s in m["_segs"] if s["st"] == "RUNNING" and s["units"] > 0]
        if budget < len(producing):
            raise ValueError("record target too small for the number of producing run segments")
        extra = budget - len(producing)
        total_dur = sum(s["e"] - s["s"] for s in producing)
        quotas = [extra * (s["e"] - s["s"]) / total_dur for s in producing]
        alloc = [int(q) for q in quotas]
        rest = extra - sum(alloc)
        for i in sorted(range(len(producing)), key=lambda i: (-(quotas[i] - alloc[i]), i))[:rest]:
            alloc[i] += 1
        self.readings = []
        for s, a in zip(producing, alloc):
            k, dur = a + 1, s["e"] - s["s"]
            for j in range(k):
                ts = s["s"] + ((j + 1) * dur) // k
                c = math.floor(s["c1"]) if j == k - 1 else math.floor(s["c0"] + (ts - s["s"]) * s["rate"])
                rd = dict(kind="PLC_READING", o=s["o"], m=s["m"], sh=s["sh"], ts=ts, counter=c, bump=0, spur=False)
                s["o"]["readings"].append(rd)
                self.readings.append(rd)
        # sensor double counts: original reading over-counts, a later manual correction fixes it
        r = self.rng("corrections")
        self.corrections = []
        for i in sorted(r.sample(range(len(self.readings)), n_corr)):
            rd = self.readings[i]
            e = r.randint(1, 8)
            rd["bump"] += e
            self.corrections.append(dict(
                kind="MANUAL_CORRECTION", o=rd["o"], m=rd["m"], sh=rd["sh"], ts=rd["ts"] + r.randint(10, 240) * 60,
                increment=-e, corrects=rd, reason="SENSOR_DOUBLE_COUNT",
                role="QUALITY_ENGINEER" if r.random() < 0.4 else "PLANT_OPERATOR"))
        for m in self.machines:
            for o in m["_orders"]:
                off = 0
                for rd in o["readings"]:
                    off += rd["bump"]
                    rd["counter"] += off

    # ------------------------------------------------------------------ 6. remaining anomalies
    def inject_count_decrease(self, n):
        r = self.rng("anomaly", "count")
        cands = []
        for m in self.machines:
            for o in m["_orders"]:
                rs = o["readings"]
                for i in range(1, len(rs)):
                    a, b = rs[i - 1], rs[i]
                    if a["sh"] is b["sh"] and a["counter"] >= 30 and b["ts"] - a["ts"] >= 2:
                        cands.append((a, b))
        for a, b in self._pick(r, cands, n, lambda c: self._ms_key(c[0]["m"], c[0]["sh"])):
            d = r.randint(5, min(40, a["counter"] - 1))
            sp = dict(kind="PLC_READING", o=a["o"], m=a["m"], sh=a["sh"], ts=a["ts"] + (b["ts"] - a["ts"]) // 2,
                      counter=a["counter"] - d, bump=0, spur=True)
            rs = a["o"]["readings"]
            rs.insert(rs.index(b), sp)
            self.add_gt("COUNT_DECREASE_NO_CORRECTION", "production_count", sp, a["m"]["machine_id"],
                        a["sh"]["shift_id"], "spurious PLC reading lower than the previous reading",
                        str(a["counter"]), str(sp["counter"]),
                        "counter_value below running maximum and no MANUAL_CORRECTION references it",
                        "reading quarantined (excluded); totals use the valid counter sequence")

    def inject_scrap(self, n):
        r = self.rng("anomaly", "scrap")
        cands = [i for i in self.inspections if i["inspection_type"] == "LOT_DISPOSITION" and i["inspected_qty"] >= 20]
        for ins in self._pick(r, cands, n, lambda c: self._ms_key(c["m"], c["sh"])):
            orig = ins["scrap_qty"]
            ins["scrap_qty"] = ins["inspected_qty"] + r.randint(1, max(2, ins["inspected_qty"] // 10))
            self.add_gt("SCRAP_EXCEEDS_TOTAL", "quality_inspection", ins, ins["m"]["machine_id"],
                        ins["sh"]["shift_id"], "scrap_qty set above the lot's counted total",
                        str(orig), str(ins["scrap_qty"]),
                        "scrap_qty + rework_qty > counted total for the order+shift lot",
                        "disposition quarantined; quality computed from remaining valid lots; row flagged")

    def inject_wrong_ict(self, n):
        r = self.rng("anomaly", "ict")
        cands = [o for m in self.machines for o in m["_orders"] if o["start"] is not None and o["cum"] >= 1]
        for o in self._pick(r, cands, n, lambda c: None):
            o["snapshot_ict"] = round(o["ict"] * r.choice([2.5, 0.4]), 1)
            self.add_gt("WRONG_IDEAL_CYCLE_TIME", "production_order", o, o["m"]["machine_id"], None,
                        "order ideal_cycle_time_s snapshot differs from its master standard",
                        str(o["ict"]), str(o["snapshot_ict"]),
                        "|order.ideal_cycle_time_s - standard.ideal_cycle_time_s| > 0.05 s",
                        "master standard used for Performance; order flagged for planner review")

    def inject_overlap(self, n):
        r = self.rng("anomaly", "overlap")
        cands = [s for m in self.machines for s in m["_segs"] if s["st"] == "RUNNING" and s["e"] - s["s"] >= 1200]
        for s in self._pick(r, cands, n, lambda c: self._ms_key(c["m"], c["sh"])):
            d = r.randint(3, 8) * 60
            start = s["s"] + r.randint(120, s["e"] - s["s"] - d - 120)
            sp = dict(s=start, e=start + d, st="STOPPED", rs="DR-UNASSIGNED", tr=None, o=s["o"], sh=s["sh"],
                      spur=True, gt=True, m=s["m"])
            s["m"]["_segs"].append(sp)
            self.add_gt("OVERLAPPING_STATE", "state_event", sp, s["m"]["machine_id"], s["sh"]["shift_id"],
                        "duplicate STOPPED event inside a RUNNING interval", None, f"{d}s overlap",
                        "two state events of one machine cover the same instant",
                        "overlap resolved by precedence PLANNED_STOP > STOPPED > CHANGEOVER > RUNNING; row flagged")
        for m in self.machines:
            m["_segs"].sort(key=lambda x: (x["s"], x["e"], x["spur"]))

    # ------------------------------------------------------------------ 7. annotations, lifecycle, truth
    def build_annotations(self):
        r = self.rng("annotations")
        self.annotations, self.true_reasons = [], []
        for m in self.machines:
            for s in m["_segs"]:
                if s["st"] != "STOPPED" or s["spur"] or s["e"] - s["s"] < C.MICRO_STOP_THRESHOLD_S:
                    continue
                self.true_reasons.append(s)
                if r.random() >= 0.93:
                    continue  # never annotated -> stays DR-UNASSIGNED
                correct = r.random() < 0.88
                code = s["tr"] if correct else r.choice([c for c in UNPLANNED_CODES if c != s["tr"]])
                a1 = dict(seg=s, reason=code, role="PLANT_OPERATOR", ts=s["e"] + r.randint(2, 90) * 60, sup=None)
                self.annotations.append(a1)
                if not correct and r.random() < 0.7:
                    self.annotations.append(dict(seg=s, reason=s["tr"], role="MAINTENANCE_ENGINEER",
                                                 ts=a1["ts"] + r.randint(60, 600) * 60, sup=a1))

    def finalize_orders(self):
        for m in self.machines:
            for o in m["_orders"]:
                runs = [s["e"] for s in m["_segs"] if s["o"] is o and s["st"] == "RUNNING"]
                units = math.floor(o["cum"])
                if o["cancelled_ts"] is not None:
                    o["status"] = "CANCELLED"
                elif o["start"] is None:
                    o["status"] = "RELEASED"
                elif o["end"] is None:
                    o["status"] = "IN_PROGRESS"
                else:
                    o["end"] = max(runs) if runs else o["end"]
                    o["status"] = "COMPLETED" if units >= C.ORDER_COMPLETION_RATIO * o["planned_qty"] else "CLOSED_SHORT"
                h = [(None, "PLANNED", o["created"], "PRODUCTION_PLANNER")]
                if o["released"] is not None:
                    h.append(("PLANNED", "RELEASED", o["released"], "PRODUCTION_PLANNER"))
                if o["status"] == "CANCELLED":
                    h.append((h[-1][1], "CANCELLED", o["cancelled_ts"], "PRODUCTION_PLANNER"))
                elif o["start"] is not None:
                    h.append(("RELEASED", "IN_PROGRESS", o["start"], "PLANT_OPERATOR"))
                    if o["status"] in ("COMPLETED", "CLOSED_SHORT"):
                        h.append(("IN_PROGRESS", o["status"], o["end"], "PLANT_OPERATOR"))
                o["history"] = h

    def build_truth(self):
        """Expected OEE per machine-shift from the simulator's own timeline (separate code path)."""
        thr = C.MICRO_STOP_THRESHOLD_S
        lots_true = {}
        for i in self.inspections:
            if i["inspection_type"] == "LOT_DISPOSITION":
                k = (i["m"]["machine_id"], i["sh"]["idx"])
                lots_true[k] = lots_true.get(k, 0) + i["true_scrap"] + i["rework_qty"]
        self.truth = []
        for m in self.machines:
            by_shift = defaultdict(list)
            for s in m["_segs"]:
                if not s["spur"]:
                    by_shift[s["sh"]["idx"]].append(s)
            for sh in self.shifts:
                planned = running = minor = unplanned = 0
                total, ideal = 0, defaultdict(int)
                for s in by_shift[sh["idx"]]:
                    dur = s["e"] - s["s"]
                    ov = sum(max(0, min(s["e"], be) - max(s["s"], bs)) for _, bs, be in sh["breaks"])
                    if s["st"] == "PLANNED_STOP":
                        planned += dur
                        continue
                    planned += ov
                    rest = dur - ov
                    if s["st"] == "RUNNING":
                        running += rest
                        total += s["units"]
                        ideal[id(s["o"])] += s["units"]
                    elif s["st"] == "STOPPED" and dur < thr:
                        minor += rest
                    else:
                        unplanned += rest
                orders = {id(s["o"]): s["o"] for s in by_shift[sh["idx"]] if s["o"] is not None}
                ideal_t = sum(u * orders[k]["ict"] for k, u in ideal.items())
                ppt = C.SHIFT_LENGTH_S - planned
                run = running + minor
                good = total - lots_true.get((m["machine_id"], sh["idx"]), 0)
                a = run / ppt if ppt > 0 else None
                p = ideal_t / run if run > 0 else None
                q = good / total if total > 0 else None
                oee = None if a is None else (0.0 if a == 0 else (a * p * q if p is not None and q is not None else None))
                self.truth.append(dict(machine_shift_key=f"{m['machine_id']}|{sh['shift_id']}",
                                       machine_id=m["machine_id"], shift_id=sh["shift_id"],
                                       planned_production_time_s=ppt, run_time_s=run, total_count=total,
                                       good_count=good, ideal_run_time_s=round(ideal_t, 3),
                                       availability=a, performance=p, quality=q, oee=oee))

    # ------------------------------------------------------------------ 8. ids & rows
    def assign_ids(self):
        all_orders = [o for m in self.machines for o in m["_orders"]]
        all_orders.sort(key=lambda o: (o["created"], o["m"]["_idx"], o["pstart"]))
        for n, o in enumerate(all_orders, 1):
            o["id"] = ids.order_id(n)
        self.all_orders = all_orders
        for m in self.machines:
            for n, s in enumerate(m["_segs"], 1):
                s["id"] = ids.event_id(m["machine_id"], n)
        for o in all_orders:
            recs = list(o["readings"]) + [c for c in self.corrections if c["o"] is o] if o["readings"] else []
            recs.sort(key=lambda x: (x["ts"], x["kind"] == "MANUAL_CORRECTION", x.get("counter") or 0))
            for n, x in enumerate(recs, 1):
                x["id"] = ids.count_id(o["id"], n)
            o["records"] = recs
        self.inspections.sort(key=lambda i: (i["ts"], i["m"]["_idx"], i["inspection_type"], i["o"]["id"]))
        for n, i in enumerate(self.inspections, 1):
            i["id"] = ids.qc_id(n)
        self.annotations.sort(key=lambda a: (a["ts"], a["seg"]["id"]))
        for n, a in enumerate(self.annotations, 1):
            a["id"] = ids.annotation_id(n)
        order_rank = {t: i for i, t in enumerate(("OVERLAPPING_STATE", "COUNT_DECREASE_NO_CORRECTION",
                                                  "SCRAP_EXCEEDS_TOTAL", "WRONG_IDEAL_CYCLE_TIME",
                                                  "DOWNTIME_OVERLAPS_BREAK"))}
        for g in self.gt:
            g["record_id"] = g["_ref"]["id"]
        self.gt.sort(key=lambda g: (order_rank[g["issue_type"]], g["record_id"]))
        for n, g in enumerate(self.gt, 1):
            g["gt_id"] = ids.gt_id(n)

    def rows(self) -> dict[str, list[dict]]:
        f = ids.fmt_ts
        out = {}
        out["plant"] = [self.plant]
        out["line"] = self.lines
        out["machine"] = self.machines
        out["product"] = self.products
        out["machine_product_standard"] = [dict(v, effective_from=f(v["_from"]),
                                                effective_to=f(v["_to"]) if v["_to"] is not None else None)
                                           for v in self.standards]
        out["downtime_reason"] = [dict(reason_code=c, description=d, category=cat, oee_loss_bucket=b,
                                       is_planned=pl, requires_annotation=ra, effective_from="2025-01-01")
                                  for c, d, cat, b, pl, ra in REASONS]
        out["shift"] = [dict(shift_id=s["shift_id"], plant_id=self.plant["plant_id"], shift_date=s["date"].isoformat(),
                             shift_code=s["code"], start_ts=f(s["s"]), end_ts=f(s["e"]), duration_s=s["e"] - s["s"],
                             is_production_scheduled=s["sched"], calendar_note=s["note"]) for s in self.shifts]
        out["shift_break"] = [dict(break_id=ids.break_id(s["shift_id"], n), shift_id=s["shift_id"], break_type=typ,
                                   start_ts=f(bs), end_ts=f(be), duration_s=be - bs)
                              for s in self.shifts for n, (typ, bs, be) in enumerate(s["breaks"], 1)]
        out["production_order"] = [dict(
            order_id=o["id"], product_id=o["p"]["product_id"], machine_id=o["m"]["machine_id"],
            standard_id=o["std"]["standard_id"], ideal_cycle_time_s=o["snapshot_ict"], planned_qty=o["planned_qty"],
            planned_start_ts=f(o["pstart"]), planned_end_ts=f(o["pend"]), created_ts=f(o["created"]),
            released_ts=f(o["released"]) if o["released"] is not None else None,
            actual_start_ts=f(o["start"]) if o["start"] is not None else None,
            actual_end_ts=f(o["end"]) if o["end"] is not None and o["status"] in ("COMPLETED", "CLOSED_SHORT") else None,
            current_status=o["status"]) for o in self.all_orders]
        out["production_order_status_event"] = [dict(
            status_event_id=ids.order_status_event_id(o["id"], n), order_id=o["id"], from_status=a, to_status=b,
            changed_ts=f(t), changed_by_role=role)
            for o in self.all_orders for n, (a, b, t, role) in enumerate(o["history"], 1)]
        out["state_event"] = [dict(
            event_id=s["id"], machine_id=m["machine_id"], shift_id=s["sh"]["shift_id"], state=s["st"],
            start_ts=f(s["s"]), end_ts=f(s["e"]), duration_s=s["e"] - s["s"], reason_code=s["rs"],
            order_id=s["o"]["id"] if s["o"] is not None else None,
            source="MES" if s["st"] in ("CHANGEOVER", "PLANNED_STOP") else "PLC")
            for m in self.machines for s in m["_segs"]]
        out["downtime_annotation"] = [dict(
            annotation_id=a["id"], event_id=a["seg"]["id"], reason_code=a["reason"], annotated_by_role=a["role"],
            annotated_ts=f(a["ts"]), supersedes_annotation_id=a["sup"]["id"] if a["sup"] else None)
            for a in self.annotations]
        counts = []
        for o in self.all_orders:
            prev = 0
            for x in o["records"]:
                if x["kind"] == "PLC_READING":
                    inc = x["counter"] - prev
                    if not x["spur"]:
                        prev = x["counter"]
                    counts.append(dict(count_id=x["id"], order_id=o["id"], machine_id=x["m"]["machine_id"],
                                       shift_id=x["sh"]["shift_id"], record_ts=f(x["ts"]), record_type=x["kind"],
                                       counter_value=x["counter"], increment_qty=inc, corrects_count_id=None,
                                       correction_reason=None, entered_by_role="OT_IT_ADMINISTRATOR"))
                else:
                    counts.append(dict(count_id=x["id"], order_id=o["id"], machine_id=x["m"]["machine_id"],
                                       shift_id=x["sh"]["shift_id"], record_ts=f(x["ts"]), record_type=x["kind"],
                                       counter_value=None, increment_qty=x["increment"],
                                       corrects_count_id=x["corrects"]["id"], correction_reason=x["reason"],
                                       entered_by_role=x["role"]))
        out["production_count"] = counts
        out["quality_inspection"] = [dict(
            inspection_id=i["id"], inspection_type=i["inspection_type"], order_id=i["o"]["id"],
            machine_id=i["m"]["machine_id"], shift_id=i["sh"]["shift_id"], inspection_ts=f(i["ts"]),
            sample_size=i.get("sample_size"), defects_found=i.get("defects_found"),
            inspected_qty=i.get("inspected_qty"), scrap_qty=i.get("scrap_qty"), rework_qty=i.get("rework_qty"),
            result=i["result"], inspector_role=i["inspector_role"]) for i in self.inspections]
        gt_rows = []
        for g in self.gt:
            gt_rows.append({k: v for k, v in g.items() if not k.startswith("_")})
        out["ground_truth_anomaly"] = gt_rows
        out["ground_truth_oee"] = self.truth
        out["ground_truth_downtime_reason"] = [dict(event_id=s["id"], true_reason_code=s["tr"])
                                               for s in self.true_reasons]
        return out

    # ------------------------------------------------------------------ driver
    def run(self) -> dict[str, list[dict]]:
        n = self.scale.anomalies_per_type
        self.build_masters()
        for m in self.machines:
            self.simulate_machine(m)
        self.inject_break_overlap(n)
        self.fill_micro_stops(reserved=n)          # n overlap events are added later
        self.compute_production()
        self.build_inspections()
        self.build_readings(reserved=n)            # n spurious readings are added later
        self.inject_count_decrease(n)
        self.inject_scrap(n)
        self.inject_wrong_ict(n)
        self.inject_overlap(n)
        self.build_annotations()
        self.finalize_orders()
        self.build_truth()
        self.assign_ids()
        return self.rows()


def generate(out_dir: str, scale: C.Scale, seed: int = C.DEFAULT_SEED) -> dict:
    gen = Generator(scale, seed)
    rows = gen.run()
    from .schema import BY_NAME
    counts = {}
    for name, rs in rows.items():
        layer = BY_NAME[name].layer
        write_table(os.path.join(out_dir, layer), name, rs)
        counts[name] = len(rs)
    return dict(row_counts=counts, stats=gen.stats)
