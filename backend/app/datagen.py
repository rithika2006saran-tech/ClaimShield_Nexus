"""Synthetic healthcare claims generator for ClaimShield Nexus.

Everything produced here is SYNTHETIC. No real PHI/PII, providers, members or codes
with real-world identity are represented. Procedure codes are used purely as labels.

Scenario injection is deliberate and seeded so that:
  * CASE-1024 / PRV-102 (hero) exercises every intelligence layer,
  * PRV-777 / PRV-778 are LEGITIMATE high-utilization controls (false-positive tests),
  * a historical, similar investigation (INV-0087 / PRV-087) exists for retrieval.

Ground-truth labels are written to separate tables (claim_labels / provider_labels)
and are only used for model training and evaluation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

N_PROVIDERS = 1000
N_MEMBERS = 12000
N_FACILITIES = 260
TARGET_BASE_REFERRALS = 2700
VOL_SCALE = 0.62
N_INVESTIGATIONS = 300

REGIONS = ["NORTH", "SOUTH", "EAST", "WEST"]
REGION_FACTOR = {"NORTH": 1.05, "SOUTH": 0.95, "EAST": 1.10, "WEST": 1.08}
CITIES = {
    "NORTH": [("Northvale", 44.9, -93.2), ("Pinecrest", 45.6, -94.1), ("Lakemont", 44.2, -92.5), ("Highfield", 46.2, -92.9)],
    "SOUTH": [("Southport", 29.8, -95.4), ("Palmetto", 30.4, -91.1), ("Sunridge", 28.5, -96.6), ("Baywood", 30.0, -90.0)],
    "EAST": [("Eastbrook", 40.7, -74.0), ("Harborview", 41.3, -72.9), ("Maplewood", 40.2, -75.1), ("Stonebridge", 39.9, -76.3)],
    "WEST": [("Westlake", 37.8, -122.3), ("Redrock", 36.1, -115.2), ("Cedar Falls", 39.5, -119.8), ("Sierra Vista", 34.1, -118.2)],
}
SURNAMES = ["Harmon", "Whitfield", "Okafor", "Lindqvist", "Marlowe", "Castellan", "Brightwater", "Ashby", "Kessler",
            "Navarro", "Thornton", "Oyelaran", "Pemberton", "Ravenscroft", "Sutherland", "Tanaka", "Vandermeer",
            "Wexler", "Yarrow", "Zimmerman", "Aldridge", "Bellamy", "Calloway", "Delacroix", "Fairbanks", "Galloway"]

FACILITY_TYPES = ["Clinic", "Hospital", "Ambulatory Surgery", "Imaging Center", "Lab", "Infusion Center"]
FACILITY_TYPE_COUNTS = {"Clinic": 100, "Hospital": 40, "Ambulatory Surgery": 40, "Imaging Center": 30, "Lab": 25, "Infusion Center": 25}

# code, description, category, em_level, base, bundle_group, is_parent, sex, min_age, max_age, facility_types, minutes
PROCEDURES = [
    ("99211", "Office visit, minimal complexity", "E/M", 1, 40, None, False, "A", 0, 120, None, 10),
    ("99212", "Office visit, low complexity", "E/M", 2, 75, None, False, "A", 0, 120, None, 15),
    ("99213", "Office visit, moderate complexity", "E/M", 3, 115, None, False, "A", 0, 120, None, 20),
    ("99214", "Office visit, moderate-high complexity", "E/M", 4, 170, None, False, "A", 0, 120, None, 30),
    ("99215", "Office visit, high complexity", "E/M", 5, 235, None, False, "A", 0, 120, None, 40),
    ("99391", "Preventive visit, child", "PREVENTIVE", None, 130, None, False, "A", 0, 17, None, 25),
    ("71046", "Chest radiograph, two views", "IMAGING", None, 95, None, False, "A", 0, 120, ["Imaging Center", "Hospital", "Clinic"], 10),
    ("73721", "MRI, lower extremity joint", "IMAGING", None, 480, None, False, "A", 0, 120, ["Imaging Center", "Hospital"], 35),
    ("74177", "CT, abdomen and pelvis with contrast", "IMAGING", None, 620, None, False, "A", 0, 120, ["Imaging Center", "Hospital"], 30),
    ("76700", "Abdominal ultrasound", "IMAGING", None, 210, None, False, "A", 0, 120, ["Imaging Center", "Hospital", "Clinic"], 25),
    ("80053", "Comprehensive metabolic panel", "LAB", None, 45, "CMP", True, "A", 0, 120, None, 5),
    ("82947", "Glucose, quantitative", "LAB", None, 12, "CMP", False, "A", 0, 120, None, 3),
    ("82565", "Creatinine, blood", "LAB", None, 14, "CMP", False, "A", 0, 120, None, 3),
    ("84132", "Potassium, serum", "LAB", None, 13, "CMP", False, "A", 0, 120, None, 3),
    ("84295", "Sodium, serum", "LAB", None, 13, "CMP", False, "A", 0, 120, None, 3),
    ("82040", "Albumin, serum", "LAB", None, 14, "CMP", False, "A", 0, 120, None, 3),
    ("85025", "Complete blood count with differential", "LAB", None, 30, "CBC", True, "A", 0, 120, None, 5),
    ("85014", "Hematocrit", "LAB", None, 8, "CBC", False, "A", 0, 120, None, 3),
    ("85018", "Hemoglobin", "LAB", None, 8, "CBC", False, "A", 0, 120, None, 3),
    ("85048", "White blood cell count", "LAB", None, 9, "CBC", False, "A", 0, 120, None, 3),
    ("97110", "Therapeutic exercise", "THERAPY", None, 55, None, False, "A", 0, 120, None, 30),
    ("97140", "Manual therapy", "THERAPY", None, 50, None, False, "A", 0, 120, None, 25),
    ("97530", "Therapeutic activities", "THERAPY", None, 60, None, False, "A", 0, 120, None, 30),
    ("93000", "Electrocardiogram, routine", "DIAGNOSTIC", None, 55, None, False, "A", 0, 120, None, 15),
    ("93306", "Echocardiography, complete", "DIAGNOSTIC", None, 380, None, False, "A", 0, 120, None, 40),
    ("93015", "Cardiovascular stress test", "DIAGNOSTIC", None, 310, None, False, "A", 0, 120, None, 45),
    ("20610", "Joint injection, major joint", "PROCEDURE", None, 140, None, False, "A", 0, 120, None, 20),
    ("29881", "Knee arthroscopy with meniscectomy", "SURGICAL", None, 3400, None, False, "A", 0, 120, ["Ambulatory Surgery", "Hospital"], 60),
    ("27447", "Total knee arthroplasty", "SURGICAL", None, 9800, None, False, "A", 0, 120, ["Ambulatory Surgery", "Hospital"], 120),
    ("11102", "Skin biopsy, single lesion", "PROCEDURE", None, 180, None, False, "A", 0, 120, None, 20),
    ("17000", "Destruction of benign lesion", "PROCEDURE", None, 150, None, False, "A", 0, 120, None, 15),
    ("96413", "Chemotherapy infusion, first hour", "INFUSION", None, 1250, None, False, "A", 0, 120, ["Infusion Center", "Hospital"], 120),
    ("96365", "Therapeutic infusion, first hour", "INFUSION", None, 410, None, False, "A", 0, 120, ["Infusion Center", "Hospital"], 60),
    ("J9035", "Oncology biologic injection", "INFUSION", None, 3200, None, False, "A", 0, 120, ["Infusion Center", "Hospital"], 30),
    ("90834", "Psychotherapy, 45 minutes", "BEHAVIORAL", None, 130, None, False, "A", 0, 120, None, 45),
    ("90837", "Psychotherapy, 60 minutes", "BEHAVIORAL", None, 175, None, False, "A", 0, 120, None, 60),
    ("90791", "Psychiatric diagnostic evaluation", "BEHAVIORAL", None, 250, None, False, "A", 0, 120, None, 60),
    ("64483", "Epidural injection, lumbar", "PROCEDURE", None, 1100, None, False, "A", 0, 120, ["Ambulatory Surgery", "Hospital"], 30),
    ("62323", "Epidural injection with imaging guidance", "PROCEDURE", None, 1250, None, False, "A", 0, 120, ["Ambulatory Surgery", "Hospital"], 35),
    ("59400", "Routine obstetric care", "OBSTETRIC", None, 3200, None, False, "F", 12, 55, None, 90),
    ("55700", "Prostate biopsy", "PROCEDURE", None, 800, None, False, "M", 18, 120, None, 30),
]
PROC = {p[0]: p for p in PROCEDURES}
BUNDLES = {"CMP": ("80053", ["82947", "82565", "84132", "84295", "82040"]), "CBC": ("85025", ["85014", "85018", "85048"])}

# specialty -> (weight in provider mix, mean monthly claims, facility types, {code: weight})
SPECIALTIES = {
    "Family Medicine": (0.18, 6.0, ["Clinic"], {"99211": .05, "99212": .12, "99213": .40, "99214": .25, "99215": .05, "99391": .06, "93000": .04, "71046": .03}),
    "Internal Medicine": (0.14, 6.0, ["Clinic", "Hospital"], {"99211": .04, "99212": .12, "99213": .40, "99214": .27, "99215": .07, "93000": .06, "71046": .04}),
    "Cardiology": (0.08, 5.0, ["Clinic", "Hospital"], {"99213": .25, "99214": .20, "99215": .05, "93000": .20, "93306": .15, "93015": .10, "99212": .05}),
    "Orthopedics": (0.08, 4.5, ["Ambulatory Surgery", "Hospital"], {"99213": .25, "99214": .15, "99215": .03, "20610": .22, "29881": .10, "27447": .05, "99212": .10, "73721": .10}),
    "Dermatology": (0.06, 5.0, ["Clinic"], {"99213": .30, "99214": .10, "11102": .32, "17000": .24, "99212": .04}),
    "Radiology": (0.08, 6.0, ["Imaging Center", "Hospital"], {"71046": .34, "73721": .16, "74177": .20, "76700": .30}),
    "Laboratory": (0.08, 8.0, ["Lab"], {"80053": .32, "85025": .30, "82947": .05, "82565": .05, "84132": .05, "84295": .05, "82040": .04, "85014": .05, "85018": .05, "85048": .04}),
    "Physical Therapy": (0.09, 7.0, ["Clinic"], {"97110": .45, "97140": .30, "97530": .25}),
    "Oncology": (0.06, 9.0, ["Infusion Center", "Hospital"], {"99214": .20, "99215": .15, "96413": .30, "96365": .25, "J9035": .10}),
    "Behavioral Health": (0.07, 5.0, ["Clinic"], {"90834": .40, "90837": .33, "90791": .05, "99213": .22}),
    "Pain Management": (0.04, 4.5, ["Ambulatory Surgery"], {"99213": .30, "99214": .20, "64483": .25, "62323": .15, "20610": .10}),
    "Obstetrics/Gynecology": (0.04, 4.5, ["Clinic", "Hospital"], {"99212": .15, "99213": .40, "99214": .20, "59400": .10, "76700": .15}),
}
PCP_SPECIALTIES = ["Family Medicine", "Internal Medicine"]

# Pinned demo entities -----------------------------------------------------------
HERO = "PRV-102"
RING_PARTNERS = {"PRV-103": "Orthopedics", "PRV-104": "Radiology", "PRV-105": "Physical Therapy"}
HUB = "PRV-410"                                    # referral hub (family medicine, WEST)
HIST_RING = {"PRV-087": "Orthopedics", "PRV-088": "Radiology", "PRV-089": "Physical Therapy"}
HIST_HUB = "PRV-085"
RING_B = {"PRV-601": "Cardiology", "PRV-602": "Radiology", "PRV-603": "Internal Medicine", "PRV-604": "Physical Therapy", "PRV-605": "Pain Management"}
CONTROLS = {"PRV-777": ("Oncology", "EAST", "FAC-200"), "PRV-778": ("Physical Therapy", "SOUTH", "FAC-201")}
PINNED_FACILITIES = {
    "FAC-012": ("Ambulatory Surgery", "WEST"), "FAC-044": ("Hospital", "WEST"), "FAC-051": ("Ambulatory Surgery", "WEST"),
    "FAC-030": ("Ambulatory Surgery", "SOUTH"), "FAC-150": ("Hospital", "EAST"), "FAC-200": ("Infusion Center", "EAST"),
    "FAC-201": ("Clinic", "SOUTH"),
}


def month_start(m: int) -> date:
    return (pd.Timestamp(config.DATA_START) + pd.DateOffset(months=m - 1)).date()


def month_end(m: int) -> date:
    return (pd.Timestamp(month_start(m)) + pd.offsets.MonthEnd(0)).date()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


class Generator:
    def __init__(self, seed: int = config.SEED):
        self.rng = np.random.default_rng(seed)
        self.claim_frames: list[pd.DataFrame] = []
        self.referral_frames: list[pd.DataFrame] = []
        self.relationships: list[dict] = []
        self.labels: dict[str, dict] = {}
        self.panels: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    # ------------------------------------------------------------------ entities
    def build_entities(self):
        rng = self.rng
        # facilities
        types = []
        for t, c in FACILITY_TYPE_COUNTS.items():
            types += [t] * c
        types = types[:N_FACILITIES]
        while len(types) < N_FACILITIES:
            types.append("Clinic")
        rng.shuffle(types)
        regions = [REGIONS[i % 4] for i in range(N_FACILITIES)]
        rng.shuffle(regions)
        fac = []
        for i in range(N_FACILITIES):
            fid = f"FAC-{i + 1:03d}"
            t, r = PINNED_FACILITIES.get(fid, (types[i], regions[i]))
            city, lat, lon = CITIES[r][int(rng.integers(0, 4))]
            fac.append({"facility_id": fid, "name": f"{city} {t} {int(rng.integers(1, 99)):02d}", "facility_type": t,
                        "region": r, "city": city, "lat": round(lat + rng.normal(0, .05), 4), "lon": round(lon + rng.normal(0, .05), 4)})
        self.facilities = pd.DataFrame(fac)

        # members
        ages = np.clip(rng.gamma(4.0, 11.0, N_MEMBERS), 0, 95).astype(int)
        sexes = rng.choice(["M", "F"], N_MEMBERS)
        mreg = rng.choice(REGIONS, N_MEMBERS)
        self.members = pd.DataFrame({"member_id": [f"MEM-{i + 1:05d}" for i in range(N_MEMBERS)], "age": ages, "sex": sexes,
                                     "region": mreg, "death_date": pd.NaT})
        dead = rng.choice(N_MEMBERS, 45, replace=False)
        dd = [month_start(int(rng.integers(3, 13))) + timedelta(days=int(rng.integers(0, 27))) for _ in dead]
        self.members.loc[dead, "death_date"] = pd.to_datetime(dd)
        self.members_by_region = {r: self.members.loc[self.members.region == r, "member_id"].to_numpy() for r in REGIONS}

        # providers
        pins: dict[str, tuple[str, str]] = {HERO: ("Orthopedics", "WEST"), HUB: ("Family Medicine", "WEST"),
                                           HIST_HUB: ("Family Medicine", "SOUTH")}
        for p, s in RING_PARTNERS.items():
            pins[p] = (s, "WEST")
        for p, s in HIST_RING.items():
            pins[p] = (s, "SOUTH")
        for p, s in RING_B.items():
            pins[p] = (s, "EAST")
        for p, (s, r, _f) in CONTROLS.items():
            pins[p] = (s, r)
        names = list(SPECIALTIES)
        w = np.array([SPECIALTIES[s][0] for s in names])
        w = w / w.sum()
        rows = []
        for i in range(1, N_PROVIDERS + 1):
            pid = f"PRV-{i:03d}"
            if pid in pins:
                spec, reg = pins[pid]
            else:
                spec = str(rng.choice(names, p=w))
                reg = str(rng.choice(REGIONS))
            city = CITIES[reg][int(rng.integers(0, 4))][0]
            enrolled = config.DATA_START - timedelta(days=int(rng.integers(200, 3000)))
            rows.append({"provider_id": pid, "display_label": f"P{i:03d}" if i < 1000 else f"P{i}", "name": f"{rng.choice(SURNAMES)} {spec.split('/')[0]} Group {i:03d}",
                         "specialty": spec, "region": reg, "city": city, "enrolled_date": enrolled})
        prov = pd.DataFrame(rows)
        # primary facilities
        prim, ptype = [], []
        fac_idx = {(r, t): self.facilities[(self.facilities.region == r) & (self.facilities.facility_type == t)].facility_id.to_numpy()
                   for r in REGIONS for t in FACILITY_TYPES}
        for _, p in prov.iterrows():
            pid = p.provider_id
            if pid in CONTROLS:
                fid = CONTROLS[pid][2]
            elif pid == HERO or pid in RING_PARTNERS:
                fid = "FAC-012"
                if pid in ("PRV-104",):
                    fid = str(rng.choice(fac_idx[("WEST", "Hospital")]))
                if pid == "PRV-105":
                    fid = str(rng.choice(fac_idx[("WEST", "Clinic")]))
                if pid == HERO:
                    fid = "FAC-012"
            elif pid in HIST_RING and pid == "PRV-087":
                fid = "FAC-030"
            else:
                t = str(rng.choice(SPECIALTIES[p.specialty][2]))
                pool = fac_idx[(p.region, t)]
                if len(pool) == 0:
                    pool = self.facilities[self.facilities.facility_type == t].facility_id.to_numpy()
                fid = str(rng.choice(pool))
            prim.append(fid)
            ptype.append(self.facilities.set_index("facility_id").loc[fid, "facility_type"])
        prov["primary_facility_id"] = prim
        prov["primary_facility_type"] = ptype
        self.providers = prov
        self.prov_idx = prov.set_index("provider_id")
        self.fac_idx_df = self.facilities.set_index("facility_id")
        self.fac_by_rt = fac_idx
        # provider -> facility list
        self.pfac: dict[str, list[str]] = {}
        for _, p in prov.iterrows():
            lst = [p.primary_facility_id]
            if rng.random() < 0.22 and p.provider_id not in CONTROLS:
                t = str(rng.choice(SPECIALTIES[p.specialty][2]))
                pool = fac_idx[(p.region, t)]
                if len(pool):
                    f2 = str(rng.choice(pool))
                    if f2 not in lst:
                        lst.append(f2)
            self.pfac[p.provider_id] = lst
            for f in lst:
                self.relationships.append({"entity_a_type": "provider", "entity_a_id": p.provider_id, "entity_b_type": "facility",
                                           "entity_b_id": f, "relationship_type": "works_at",
                                           "start_date": p.enrolled_date, "source": "enrollment"})
        self.procedures = pd.DataFrame([{
            "code": p[0], "description": p[1], "category": p[2], "em_level": p[3], "base_amount": p[4], "bundle_group": p[5],
            "is_bundle_parent": p[6], "allowed_sex": p[7], "min_age": p[8], "max_age": p[9],
            "facility_types": "|".join(p[10]) if p[10] else "", "service_minutes": p[11], "repeat_same_day_ok": False} for p in PROCEDURES])
        self.procedures["em_level"] = self.procedures["em_level"].astype("Int64")

    def add_works_at(self, pid: str, fid: str, start: date, source: str = "scenario"):
        if fid not in self.pfac[pid]:
            self.pfac[pid].append(fid)
        self.relationships.append({"entity_a_type": "provider", "entity_a_id": pid, "entity_b_type": "facility", "entity_b_id": fid,
                                   "relationship_type": "works_at", "start_date": start, "source": source})

    def add_assoc(self, a: str, b: str, start: date, source: str = "scenario"):
        self.relationships.append({"entity_a_type": "provider", "entity_a_id": a, "entity_b_type": "provider", "entity_b_id": b,
                                   "relationship_type": "associated_with", "start_date": start, "source": source})

    # ------------------------------------------------------------------ helpers
    def panel(self, pid: str, size: int) -> tuple[np.ndarray, np.ndarray]:
        if pid not in self.panels:
            reg = self.prov_idx.loc[pid, "region"]
            pool = self.members_by_region[reg]
            members = self.rng.choice(pool, size=min(size, len(pool)), replace=False)
            w = self.rng.exponential(1.0, len(members))
            self.panels[pid] = (members, w / w.sum())
        return self.panels[pid]

    def sample_codes(self, spec: str, n: int) -> np.ndarray:
        codes = list(SPECIALTIES[spec][3])
        p = np.array([SPECIALTIES[spec][3][c] for c in codes], float)
        return self.rng.choice(codes, size=n, p=p / p.sum())

    def rand_dates(self, start: date, end: date, n: int) -> np.ndarray:
        span = max((end - start).days, 0) + 1
        offs = self.rng.integers(0, span, n)
        return (pd.Timestamp(start) + pd.to_timedelta(offs, unit="D")).to_numpy()

    def rows(self, pid, dates, codes, members, facilities, referrers=None, scenario="baseline", injected=False) -> pd.DataFrame:
        n = len(dates)
        return pd.DataFrame({
            "provider_id": pid, "member_id": members, "referring_provider_id": referrers if referrers is not None else [None] * n,
            "facility_id": facilities, "service_date": pd.to_datetime(dates), "procedure_code": codes, "units": 1,
            "injected_fwa": injected, "scenario": scenario})

    def fac_choices(self, pid: str, n: int, weights=None) -> np.ndarray:
        fl = self.pfac[pid]
        if weights is None:
            weights = [0.9] + [0.1 / max(len(fl) - 1, 1)] * (len(fl) - 1) if len(fl) > 1 else [1.0]
        w = np.array(weights, float)
        return self.rng.choice(fl, size=n, p=w / w.sum())

    def label(self, pid: str, role: str, scenario: str, start: date | None = None, notes: str = ""):
        cur = self.labels.setdefault(pid, {"provider_id": pid, "role": "normal", "scenarios": [], "scenario_start": None, "notes": ""})
        order = ["normal", "historical", "ring", "injected", "control", "hero"]
        if order.index(role) > order.index(cur["role"]):
            cur["role"] = role
        if scenario and scenario not in cur["scenarios"]:
            cur["scenarios"].append(scenario)
        if start and (cur["scenario_start"] is None or start < cur["scenario_start"]):
            cur["scenario_start"] = start
        if notes:
            cur["notes"] = (cur["notes"] + " " + notes).strip()

    def add(self, df: pd.DataFrame):
        if len(df):
            self.claim_frames.append(df)

    # ------------------------------------------------------------------ baseline
    def build_baseline(self):
        rng = self.rng
        lam_override = {HERO: 3.8, HUB: 3.5, HIST_HUB: 3.5}
        late_start = set(rng.choice(self.providers.provider_id.to_numpy(), 70, replace=False))
        for _, p in self.providers.iterrows():
            pid, spec = p.provider_id, p.specialty
            if pid in CONTROLS:
                continue  # controls generated separately
            lam = lam_override.get(pid, SPECIALTIES[spec][1] * VOL_SCALE * rng.lognormal(0, 0.45))
            first_m = int(rng.integers(5, 12)) if pid in late_start and pid not in {HERO, HUB, *RING_PARTNERS, *RING_B, *HIST_RING} else 1
            counts = [int(rng.poisson(lam * (1 + 0.06 * np.sin(m / 2.0)))) if m >= first_m else 0 for m in range(1, config.N_MONTHS + 1)]
            n = sum(counts)
            if n == 0:
                continue
            dates = np.concatenate([self.rand_dates(month_start(m), month_end(m), c) for m, c in enumerate(counts, 1) if c])
            panel, w = self.panel(pid, max(10, int(n / 2.2)))
            members = rng.choice(panel, size=n, p=w)
            self.add(self.rows(pid, dates, self.sample_codes(spec, n), members, self.fac_choices(pid, n)))
        self.claims = pd.concat(self.claim_frames, ignore_index=True)
        self.claim_frames = [self.claims]
        self._build_controls()

    def _build_controls(self):
        rng = self.rng
        # PRV-777: oncology infusion, repeated cycles every 21 days per member (legitimate, high utilization)
        pid = "PRV-777"
        panel = rng.choice(self.members_by_region["EAST"], 7, replace=False)
        frames = []
        for mem in panel:
            d = month_start(1) + timedelta(days=int(rng.integers(0, 21)))
            code = rng.choice(["96413", "96365", "J9035"], p=[.5, .3, .2])
            while d <= config.DATA_END:
                frames.append((d, mem, code if rng.random() < .85 else "99214"))
                d += timedelta(days=21 + int(rng.integers(-1, 2)))
        df = pd.DataFrame(frames, columns=["service_date", "member_id", "procedure_code"])
        self.add(self.rows(pid, df.service_date.to_numpy(), df.procedure_code.to_numpy(), df.member_id.to_numpy(), ["FAC-200"] * len(df),
                           scenario="legit_high_utilization"))
        self.label(pid, "control", "legit_high_utilization", None, "Legitimate high utilization: oncology infusion cycles")
        # PRV-778: PT with consecutive-day visits (legitimate), not same-day repeats
        pid = "PRV-778"
        panel = rng.choice(self.members_by_region["SOUTH"], 13, replace=False)
        frames = []
        for mem in panel:
            for _ in range(int(rng.integers(2, 5))):
                d = month_start(1) + timedelta(days=int(rng.integers(0, 520)))
                for k in range(int(rng.integers(3, 6))):
                    if d + timedelta(days=k) <= config.DATA_END:
                        frames.append((d + timedelta(days=k), mem, str(rng.choice(["97110", "97140", "97530"], p=[.5, .3, .2]))))
        df = pd.DataFrame(frames, columns=["service_date", "member_id", "procedure_code"])
        self.add(self.rows(pid, df.service_date.to_numpy(), df.procedure_code.to_numpy(), df.member_id.to_numpy(), ["FAC-201"] * len(df),
                           scenario="legit_high_utilization"))
        self.label(pid, "control", "legit_high_utilization", None, "Legitimate high utilization: PT episodes of care")
        self.claims = pd.concat(self.claim_frames, ignore_index=True)
        self.claim_frames = [self.claims]

    # ------------------------------------------------------------------ scenario primitives
    def _take(self) -> pd.DataFrame:
        self.claims = pd.concat(self.claim_frames, ignore_index=True)
        self.claim_frames = [self.claims]
        return self.claims

    def _commit(self, claims: pd.DataFrame):
        self.claims = claims.reset_index(drop=True)
        self.claim_frames = [self.claims]

    def scn_duplicate(self, pid, start: date, end: date, prob: float, scenario="duplicate", role="injected"):
        c = self._take()
        m = (c.provider_id == pid) & (c.service_date >= pd.Timestamp(start)) & (c.service_date <= pd.Timestamp(end)) & ~c.scenario.str.contains("duplicate")
        src = c[m]
        pick = src[self.rng.random(len(src)) < prob].copy()
        pick["scenario"] = scenario
        pick["injected_fwa"] = True
        pick["_dup"] = True
        self.add(pick)
        self.label(pid, role, "duplicate", start)

    def scn_upcoding(self, pid, start: date, end: date, prob=0.65):
        c = self._take()
        m = (c.provider_id == pid) & (c.service_date >= pd.Timestamp(start)) & (c.service_date <= pd.Timestamp(end)) & c.procedure_code.isin(["99211", "99212", "99213", "99214"]) & ~c.injected_fwa
        idx = c.index[m][self.rng.random(m.sum()) < prob]
        c.loc[idx, "procedure_code"] = self.rng.choice(["99215", "99215", "99214"], len(idx))
        c.loc[idx, "scenario"] = "upcoding"
        c.loc[idx, "injected_fwa"] = True
        self._commit(c)
        # additional visit volume billed at high complexity
        spec = self.prov_idx.loc[pid, "specialty"]
        base = SPECIALTIES[spec][1] * VOL_SCALE
        reg = self.prov_idx.loc[pid, "region"]
        pool = self.rng.choice(self.members_by_region[reg], 90, replace=False)
        for m in range(1, config.N_MONTHS + 1):
            ms, me = max(month_start(m), start), min(month_end(m), end)
            if ms > me:
                continue
            n = int(self.rng.poisson(base * 1.3))
            if n:
                self.add(self.rows(pid, self.rand_dates(ms, me, n), self.rng.choice(["99214", "99215", "99215"], n), self.rng.choice(pool, n),
                                   self.fac_choices(pid, n), scenario="upcoding", injected=True))
        self.label(pid, "injected", "upcoding", start)

    def scn_unbundling(self, pid, start: date, end: date, prob=0.9):
        c = self._take()
        m = (c.provider_id == pid) & (c.service_date >= pd.Timestamp(start)) & (c.service_date <= pd.Timestamp(end)) & c.procedure_code.isin(["80053", "85025"])
        idx = c.index[m][self.rng.random(m.sum()) < prob]
        new = []
        for i in idx:
            r = c.loc[i]
            comps = BUNDLES["CMP" if r.procedure_code == "80053" else "CBC"][1]
            take = list(self.rng.choice(comps, size=min(len(comps), 4 if r.procedure_code == "80053" else 3), replace=False))
            for code in take:
                d = r.to_dict()
                d.update(procedure_code=code, scenario="unbundling", injected_fwa=True)
                new.append(d)
        c = c.drop(index=idx)
        self._commit(c)
        if new:
            self.add(pd.DataFrame(new))
        self.label(pid, "injected", "unbundling", start)

    def scn_implausible(self, pid, start: date, end: date, n: int):
        rng = self.rng
        spec_fac = self.pfac[pid][0]
        ftype = self.fac_idx_df.loc[spec_fac, "facility_type"]
        dead = self.members[self.members.death_date.notna()]
        rows = []
        for k in range(n):
            kind = k % 4
            d = self.rand_dates(start, end, 1)[0]
            if kind == 0:  # service after member death (phantom service)
                r = dead.iloc[int(rng.integers(0, len(dead)))]
                dd = pd.Timestamp(r.death_date) + pd.Timedelta(days=int(rng.integers(5, 120)))
                if dd > pd.Timestamp(config.DATA_END):
                    dd = pd.Timestamp(config.DATA_END)
                rows.append((dd, r.member_id, "99214", spec_fac, "implausible_service"))
            elif kind == 1:  # sex-restricted code for wrong sex
                mem = self.members[self.members.sex == "M"].member_id.iloc[int(rng.integers(0, 3000))]
                rows.append((d, mem, "59400", spec_fac, "implausible_service"))
            elif kind == 2:  # pediatric preventive code for an adult
                mem = self.members[self.members.age > 40].member_id.iloc[int(rng.integers(0, 3000))]
                rows.append((d, mem, "99391", spec_fac, "implausible_service"))
            else:  # surgery code billed at a facility type that cannot perform it
                if ftype in ("Clinic", "Lab", "Imaging Center", "Infusion Center"):
                    mem = self.members.member_id.iloc[int(rng.integers(0, N_MEMBERS))]
                    rows.append((d, mem, "27447", spec_fac, "implausible_service"))
                else:
                    mem = self.members[self.members.sex == "F"].member_id.iloc[int(rng.integers(0, 3000))]
                    rows.append((d, mem, "55700", spec_fac, "implausible_service"))
        df = pd.DataFrame(rows, columns=["service_date", "member_id", "procedure_code", "facility_id", "scenario"])
        self.add(self.rows(pid, df.service_date.to_numpy(), df.procedure_code.to_numpy(), df.member_id.to_numpy(), df.facility_id.to_numpy(),
                           scenario="implausible_service", injected=True))
        self.label(pid, "injected", "implausible_service", start)

    def scn_excessive(self, pid, start: date, end: date, mult: float, scenario="excessive_utilization", role="injected"):
        rng = self.rng
        spec = self.prov_idx.loc[pid, "specialty"]
        base = SPECIALTIES[spec][1] * VOL_SCALE
        reg = self.prov_idx.loc[pid, "region"]
        pool = rng.choice(self.members_by_region[reg], 160, replace=False)
        for m in range(1, config.N_MONTHS + 1):
            ms, me = max(month_start(m), start), min(month_end(m), end)
            if ms > me:
                continue
            n = int(rng.poisson(base * mult * 0.8))
            if n == 0:
                continue
            self.add(self.rows(pid, self.rand_dates(ms, me, n), self.sample_codes(spec, n), rng.choice(pool, n), self.fac_choices(pid, n),
                               scenario=scenario, injected=True))
        self.label(pid, role, scenario, start)

    def scn_timing(self, pid, start: date, end: date, kind: str):
        rng = self.rng
        spec = self.prov_idx.loc[pid, "specialty"]
        reg = self.prov_idx.loc[pid, "region"]
        pool = rng.choice(self.members_by_region[reg], 120, replace=False)
        days = pd.date_range(start, end, freq="5D")
        frames = []
        if kind == "volume":
            fac = self.pfac[pid][0]
            for d in days:
                n = int(rng.integers(24, 32))
                codes = np.where(rng.random(n) < .5, "99214", "97110") if spec == "Physical Therapy" else self.sample_codes(spec, n)
                f = self.rows(pid, [d] * n, codes, rng.choice(pool, n), [fac] * n, scenario="impossible_timing", injected=True)
                f["minutes_override"] = rng.integers(38, 52, n)
                frames.append(f)
        else:  # two distant facilities on the same day
            far_region = [r for r in REGIONS if r != reg][int(rng.integers(0, 3))]
            ftype = self.prov_idx.loc[pid, "primary_facility_type"]
            pool_f = self.fac_by_rt[(far_region, ftype)] if len(self.fac_by_rt[(far_region, ftype)]) else self.fac_by_rt[(far_region, "Clinic")]
            far = str(rng.choice(pool_f))
            self.add_works_at(pid, far, start)
            near = self.pfac[pid][0]
            for d in days:
                for fac in (near, far):
                    n = int(rng.integers(3, 6))
                    f = self.rows(pid, [d] * n, self.sample_codes(spec, n), rng.choice(pool, n), [fac] * n, scenario="impossible_timing", injected=True)
                    frames.append(f)
        self.add(pd.concat(frames, ignore_index=True))
        self.label(pid, "injected", "impossible_timing", start)

    def referral_flow(self, referrer: str, target: str, n: int, start: date, end: date, scenario: str, injected=True,
                      member_region: str | None = None, codes: np.ndarray | None = None, fac: str | None = None):
        """Create n referrals referrer->target and the target's resulting claims."""
        rng = self.rng
        spec = self.prov_idx.loc[target, "specialty"]
        reg = member_region or self.prov_idx.loc[target, "region"]
        members = rng.choice(self.members_by_region[reg], n)
        dates = self.rand_dates(start, end, n)
        codes = codes if codes is not None else self.sample_codes(spec, n)
        facs = [fac] * n if fac else self.fac_choices(target, n)
        self.add(self.rows(target, dates, codes, members, facs, referrers=[referrer] * n, scenario=scenario, injected=injected))
        ref_dates = pd.Series(pd.to_datetime(dates) - pd.to_timedelta(rng.integers(2, 9, n), unit="D"))
        self.referral_frames.append(pd.DataFrame({"referring_provider_id": referrer, "target_provider_id": target, "target_facility_id": list(facs),
                                                  "member_id": members, "referral_date": ref_dates.clip(lower=pd.Timestamp(config.DATA_START)).to_numpy()}))

    # ------------------------------------------------------------------ scenarios
    def inject_scenarios(self):
        rng = self.rng
        reserved = {HERO, HUB, HIST_HUB, *RING_PARTNERS, *HIST_RING, *RING_B, *CONTROLS}
        pool = [p for p in self.providers.provider_id if p not in reserved]
        rng.shuffle(pool)
        take = lambda pred, k: [pool.pop(next(i for i, p in enumerate(pool) if pred(self.prov_idx.loc[p]))) for _ in range(k)]
        sd = lambda lo, hi: month_start(int(rng.integers(lo, hi + 1))) + timedelta(days=int(rng.integers(0, 20)))
        END = config.DATA_END
        self.scenario_providers: dict[str, list[str]] = {}

        # -- duplicate billing
        for pid in take(lambda p: p.specialty in ("Family Medicine", "Internal Medicine", "Cardiology", "Dermatology", "Behavioral Health") and p.name not in self.labels, 14):
            s = sd(6, 13)
            self.scn_excessive(pid, s, END, 0.8, scenario="duplicate", role="injected")  # raised volume with resubmissions
            self.scn_duplicate(pid, s, END, 0.35)
            self.scenario_providers.setdefault("duplicate", []).append(pid)
        # -- upcoding
        for pid in take(lambda p: p.specialty in ("Family Medicine", "Internal Medicine", "Cardiology", "Orthopedics", "Obstetrics/Gynecology", "Pain Management"), 12):
            self.scn_upcoding(pid, sd(5, 12), END, 0.7)
            self.scenario_providers.setdefault("upcoding", []).append(pid)
        # -- unbundling
        for pid in take(lambda p: p.specialty == "Laboratory", 8):
            self.scn_unbundling(pid, sd(5, 13), END)
            self.scenario_providers.setdefault("unbundling", []).append(pid)
        # -- implausible / phantom
        for pid in take(lambda p: p.specialty in ("Family Medicine", "Dermatology", "Internal Medicine"), 6):
            self.scn_implausible(pid, sd(6, 13), END, int(rng.integers(24, 40)))
            self.scenario_providers.setdefault("implausible", []).append(pid)
        # -- excessive utilization
        for pid in take(lambda p: p.specialty not in ("Oncology",), 10):
            self.scn_excessive(pid, sd(6, 13), END, float(rng.uniform(3.0, 4.6)))
            self.scenario_providers.setdefault("excessive", []).append(pid)
        # -- impossible timing
        tp = take(lambda p: p.specialty in ("Family Medicine", "Internal Medicine", "Physical Therapy", "Behavioral Health", "Dermatology"), 6)
        for i, pid in enumerate(tp):
            self.scn_timing(pid, sd(7, 12), END, "volume" if i % 2 == 0 else "geo")
            self.scenario_providers.setdefault("timing", []).append(pid)
        # -- referral concentration: targets with one dominant referrer
        for pid in take(lambda p: p.specialty in ("Radiology", "Orthopedics", "Cardiology", "Physical Therapy", "Pain Management"), 10):
            ref = next(p for p in pool if self.prov_idx.loc[p].specialty in PCP_SPECIALTIES and self.prov_idx.loc[p].region == self.prov_idx.loc[pid].region)
            pool.remove(ref)
            s = sd(6, 12)
            for m in range(1, config.N_MONTHS + 1):
                ms, me = max(month_start(m), s), month_end(m)
                if ms <= me:
                    self.referral_flow(ref, pid, int(rng.poisson(9)), ms, me, "referral_concentration")
            self.label(pid, "injected", "referral_concentration", s)
            self.label(ref, "injected", "referral_concentration", s, "referral source")
            self.scenario_providers.setdefault("referral", []).append(pid)

        self._hero()
        self._ring_b()
        self._historical()

    def _hero(self):
        rng = self.rng
        END = config.DATA_END
        hero, hub = HERO, HUB
        spec = "Orthopedics"
        reg = "WEST"
        pool = rng.choice(self.members_by_region[reg], 240, replace=False)
        # facility timeline: new facility relationships appear in month 12
        self.add_works_at(hero, "FAC-044", month_start(12), "hero_scenario")
        self.add_works_at(hero, "FAC-051", month_start(12), "hero_scenario")
        for p in (*RING_PARTNERS, hub):
            self.add_works_at(p, "FAC-012", month_start(12 if p != "PRV-105" else 13), "hero_scenario")
        # utilization increase: extra claims, ramping
        extra = {7: 3, 8: 4, 9: 7, 10: 9, 11: 12, 12: 14, 13: 18, 14: 21, 15: 23, 16: 25, 17: 26, 18: 28}
        for m, lam in extra.items():
            n = int(rng.poisson(lam))
            ms, me = month_start(m), month_end(m)
            # referral concentration from the hub begins in month 9
            share = 0.0 if m < 9 else min(0.75, 0.35 + 0.05 * (m - 9))
            nref = int(round(n * share))
            if nref:
                self.referral_flow(hub, hero, nref, ms, me, "hero_referral_concentration", member_region=reg, fac=None)
            rest = n - nref
            if rest > 0:
                self.add(self.rows(hero, self.rand_dates(ms, me, rest), self.sample_codes(spec, rest), rng.choice(pool, rest), self.fac_choices(hero, rest),
                                   scenario="hero_utilization", injected=True))
        # the hub's own baseline: a few non-hero referrals before month 9 (so concentration visibly shifts)
        for m in range(2, 9):
            tgt = next(p for p in self.providers.provider_id if self.prov_idx.loc[p].region == reg and self.prov_idx.loc[p].specialty in ("Cardiology", "Radiology", "Dermatology") and p not in (hero, *RING_PARTNERS))
            self.referral_flow(hub, tgt, 2, month_start(m), month_end(m), "baseline", injected=False)
        self.label(hub, "ring", "referral_concentration", month_start(9), "referral source of PRV-102")
        c = self._take()
        # new facility relationships (month 12+): move a share of hero claims to the new facilities
        m_new = (c.provider_id == hero) & (c.service_date >= pd.Timestamp(month_start(12)))
        r = rng.random(len(c))
        c.loc[m_new & (r < 0.14), "facility_id"] = "FAC-044"
        c.loc[m_new & (r >= 0.14) & (r < 0.26), "facility_id"] = "FAC-051"
        # high-value procedure shift (month 13+): knee arthroplasty share rises
        m_hv = (c.provider_id == hero) & (c.service_date >= pd.Timestamp(month_start(13)))
        r2 = rng.random(len(c))
        hv = m_hv & (r2 < 0.30)
        c.loc[hv, "procedure_code"] = "27447"
        c.loc[hv, "scenario"] = "hero_high_value"
        c.loc[hv, "injected_fwa"] = True
        c.loc[hv & ~c.facility_id.isin(["FAC-012", "FAC-044", "FAC-051"]), "facility_id"] = "FAC-012"
        self._commit(c)
        # duplicates from month 11
        self.scn_duplicate(hero, month_start(11), END, 0.28, scenario="hero_duplicate", role="hero")
        # coordinated partners receive referrals from the hero and the hub (months 13-18)
        for p, s_ in RING_PARTNERS.items():
            start_m = 13 if p != "PRV-105" else 14
            for m in range(start_m, 19):
                self.referral_flow(hero, p, int(rng.poisson(8)), month_start(m), month_end(m), "hero_ring")
                self.referral_flow(hub, p, int(rng.poisson(3)), month_start(m), month_end(m), "hero_ring")
            self.label(p, "ring", "coordinated_network", month_start(start_m), "partner of PRV-102")
            self.add_assoc(hero, p, month_start(12 if p != "PRV-105" else 14), "hero_scenario")
        self.add_assoc("PRV-103", "PRV-104", month_start(13), "hero_scenario")
        self.add_assoc("PRV-104", "PRV-105", month_start(14), "hero_scenario")
        self.add_assoc(hero, hub, month_start(10), "hero_scenario")
        # network expansion months 15-17: small referral links to additional WEST providers
        cand = [p for p in self.providers.provider_id if self.prov_idx.loc[p].region == reg and p not in (hero, hub, *RING_PARTNERS)
                and self.prov_idx.loc[p].specialty in ("Radiology", "Cardiology", "Physical Therapy", "Pain Management", "Laboratory")]
        for p in rng.choice(cand, 11, replace=False):
            m = int(rng.integers(16, 19))
            st = max(month_start(m), date(2026, 7, 14))
            self.referral_flow(hero, str(p), int(rng.integers(3, 7)), st, month_end(m), "hero_network_expansion")
            self.add_assoc(hero, str(p), st, "hero_scenario")
        self.label(hero, "hero", "hero_multi_pattern", month_start(7), "Hero case: staged escalation (utilization, referral concentration, duplicates, new facilities, high-value procedures, network expansion)")

    def _ring_b(self):
        rng = self.rng
        ids = list(RING_B)
        for p in ids:
            self.add_works_at(p, "FAC-150", month_start(10), "ring_b")
        for i, p in enumerate(ids):
            q = ids[(i + 1) % len(ids)]
            for m in range(10, 19):
                self.referral_flow(p, q, int(rng.poisson(6)), month_start(m), month_end(m), "coordinated_network")
            self.add_assoc(p, q, month_start(10), "ring_b")
            self.label(p, "injected", "coordinated_network", month_start(10))
        for p in ("PRV-602", "PRV-604"):
            self.scn_duplicate(p, month_start(12), config.DATA_END, 0.18, scenario="duplicate", role="injected")
        extra = [x for x in self.providers.provider_id if self.prov_idx.loc[x].region == "EAST" and x not in RING_B][:6]
        for k, x in enumerate(extra):
            self.add_assoc(ids[k % 5], x, month_start(13 + k % 3), "ring_b")

    def _historical(self):
        """Past scenarios (months 1-7) with closed investigations. Includes the pinned similar case INV-0087."""
        rng = self.rng
        hub = HIST_HUB
        # pinned historical ring around PRV-087: duplicate + referral concentration + shared facility + network expansion
        for p in HIST_RING:
            self.add_works_at(p, "FAC-030", month_start(2), "hist_ring")
        for m in range(2, 8):
            self.referral_flow(hub, "PRV-087", int(rng.poisson(13)), month_start(m), month_end(m), "historical_referral_concentration")
            for q in ("PRV-088", "PRV-089"):
                self.referral_flow("PRV-087", q, int(rng.poisson(5)), month_start(m), month_end(m), "historical_ring")
        self.scn_duplicate("PRV-087", month_start(3), month_end(7), 0.30, scenario="historical_duplicate", role="historical")
        for q in ("PRV-088", "PRV-089"):
            self.add_assoc("PRV-087", q, month_start(3), "hist_ring")
        self.add_assoc("PRV-088", "PRV-089", month_start(4), "hist_ring")
        self.add_assoc("PRV-087", hub, month_start(2), "hist_ring")
        self.label("PRV-087", "historical", "historical_pinned_similar_case", month_start(2))
        self.label(hub, "historical", "referral_concentration", month_start(2))
        for q in ("PRV-088", "PRV-089"):
            self.label(q, "historical", "coordinated_network", month_start(2))
        # other historical scenario providers (they behaved suspiciously early, then stopped)
        reserved = {HERO, HUB, HIST_HUB, *RING_PARTNERS, *HIST_RING, *RING_B, *CONTROLS}
        used = set(self.labels)
        cands = [p for p in self.providers.provider_id if p not in reserved and p not in used]
        rng.shuffle(cands)
        self.hist_scenario_providers: list[tuple[str, str]] = []
        kinds = ["duplicate", "upcoding", "excessive", "referral_concentration", "unbundling"]
        for i, pid in enumerate(cands[:40]):
            spec = self.prov_idx.loc[pid].specialty
            kind = kinds[i % 5]
            if kind == "unbundling" and spec != "Laboratory":
                kind = "duplicate"
            if kind == "upcoding" and spec not in ("Family Medicine", "Internal Medicine", "Cardiology", "Orthopedics", "Obstetrics/Gynecology", "Pain Management"):
                kind = "excessive"
            s, e = month_start(int(rng.integers(1, 3))), month_end(int(rng.integers(5, 8)))
            if kind == "duplicate":
                self.scn_excessive(pid, s, e, 0.8, scenario="historical_duplicate", role="historical")
                self.scn_duplicate(pid, s, e, 0.35, scenario="historical_duplicate", role="historical")
            elif kind == "upcoding":
                self.scn_upcoding(pid, s, e, 0.7)
                self.labels[pid]["role"] = "historical"
            elif kind == "excessive":
                self.scn_excessive(pid, s, e, 3.5, scenario="historical_excessive", role="historical")
            elif kind == "unbundling":
                self.scn_unbundling(pid, s, e)
                self.labels[pid]["role"] = "historical"
            else:
                ref = next(p for p in cands[40:] if self.prov_idx.loc[p].specialty in PCP_SPECIALTIES and self.prov_idx.loc[p].region == self.prov_idx.loc[pid].region)
                for m in range(1, 8):
                    ms, me = max(month_start(m), s), min(month_end(m), e)
                    if ms <= me:
                        self.referral_flow(ref, pid, int(rng.poisson(8)), ms, me, "historical_referral_concentration")
                self.label(pid, "historical", "referral_concentration", s)
            self.hist_scenario_providers.append((pid, kind))

    # ------------------------------------------------------------------ finalize
    def finalize(self):
        rng = self.rng
        c = self._take().copy()
        if "_dup" not in c:
            c["_dup"] = False
        c["_dup"] = c["_dup"].fillna(False).astype(bool)
        # accidental resubmission noise (not FWA ground truth)
        base = c[(~c.injected_fwa) & (~c.scenario.eq("legit_high_utilization")) & (~c._dup)]
        noise = base.sample(int(len(base) * 0.002), random_state=7).copy()
        noise["scenario"] = "noise_duplicate"
        noise["_dup"] = True
        c = pd.concat([c, noise], ignore_index=True)
        # drop claims for members after death except implausible scenario
        d = c.merge(self.members[["member_id", "death_date"]], on="member_id", how="left")
        bad = d.death_date.notna() & (d.service_date > d.death_date) & ~d.scenario.eq("implausible_service")
        c = c.loc[~bad.to_numpy()].reset_index(drop=True)
        # enforce eligibility for non-scenario rows (age/sex/facility) by re-coding to a visit
        mm = self.members.set_index("member_id")
        pr = self.procedures.set_index("code")
        age = c.member_id.map(mm.age)
        sex = c.member_id.map(mm.sex)
        ftype = c.facility_id.map(self.fac_idx_df.facility_type)
        asex = c.procedure_code.map(pr.allowed_sex)
        viol = ((asex != "A") & (asex != sex)) | (age < c.procedure_code.map(pr.min_age)) | (age > c.procedure_code.map(pr.max_age))
        fts = c.procedure_code.map(pr.facility_types)
        viol |= fts.ne("") & ~pd.Series([(ft in fl.split("|")) if fl else True for ft, fl in zip(ftype, fts)], index=c.index)
        fix = viol & ~c.scenario.eq("implausible_service")
        c.loc[fix, "procedure_code"] = "99213"
        # a handful of random coding errors that are NOT FWA ground truth
        err = rng.choice(c.index[(~c.injected_fwa) & (c.scenario == "baseline")], 8, replace=False)
        c.loc[err, "procedure_code"] = "59400"
        c.loc[err, "member_id"] = rng.choice(self.members[self.members.sex == "M"].member_id.to_numpy(), len(err))
        c.loc[err, "scenario"] = "noise_coding_error"
        # monetary fields
        base_amt = c.procedure_code.map(pr.base_amount).astype(float)
        regf = c.facility_id.map(self.fac_idx_df.region).map(REGION_FACTOR)
        allowed = (base_amt * regf * rng.lognormal(0, 0.10, len(c))).round(2)
        c["allowed_amount"] = allowed
        c["paid_amount"] = (allowed * rng.uniform(0.78, 0.92, len(c))).round(2)
        c["billed_amount"] = (allowed * rng.uniform(1.25, 2.0, len(c))).round(2)
        mins = c.procedure_code.map(pr.service_minutes).astype(float) * rng.uniform(0.85, 1.15, len(c))
        if "minutes_override" in c:
            mins = c["minutes_override"].where(c["minutes_override"].notna(), mins)
        c["service_minutes"] = mins.round().astype(int)
        lag = rng.integers(1, 22, len(c))
        c["submit_date"] = (c.service_date + pd.to_timedelta(lag, unit="D")).clip(upper=pd.Timestamp(config.DATA_END))
        duplicates = c._dup
        c.loc[duplicates, "submit_date"] = (c.loc[duplicates, "submit_date"] + pd.to_timedelta(rng.integers(1, 5, int(duplicates.sum())), unit="D")).clip(upper=pd.Timestamp(config.DATA_END))
        cat = c.procedure_code.map(pr.category)
        c["claim_type"] = cat.map({"E/M": "PROFESSIONAL", "PREVENTIVE": "PROFESSIONAL", "IMAGING": "IMAGING", "LAB": "LAB", "THERAPY": "THERAPY",
                                   "DIAGNOSTIC": "DIAGNOSTIC", "PROCEDURE": "PROCEDURE", "SURGICAL": "FACILITY", "INFUSION": "OUTPATIENT",
                                   "BEHAVIORAL": "PROFESSIONAL", "OBSTETRIC": "PROFESSIONAL"}).fillna("PROFESSIONAL")
        c = c.sort_values(["service_date", "provider_id", "member_id"]).reset_index(drop=True)
        c["claim_id"] = [f"CLM-{i + 1:06d}" for i in range(len(c))]
        self.claims = c

        # baseline referrals from specialist claims
        rng = self.rng
        tgt_specs = [s for s in SPECIALTIES if s not in PCP_SPECIALTIES and s != "Laboratory"]
        special = {HUB, HERO, *RING_PARTNERS, *RING_B, *HIST_RING, HIST_HUB, *CONTROLS}
        cand = c[(c.referring_provider_id.isna()) & c.provider_id.map(self.prov_idx.specialty).isin(tgt_specs) & ~c.injected_fwa & ~c.provider_id.isin(special)
                 & ~c.scenario.str.startswith(("historical", "hero", "legit"))]
        pick = cand.sample(min(TARGET_BASE_REFERRALS, len(cand)), random_state=11)
        pcps = self.providers[self.providers.specialty.isin(PCP_SPECIALTIES) & ~self.providers.provider_id.isin(special)]
        by_region = {r: pcps[pcps.region == r].provider_id.to_numpy() for r in REGIONS}
        usual: dict[str, np.ndarray] = {}
        out_ref, ref_rows = {}, []
        for idx, row in pick.iterrows():
            t = row.provider_id
            if t not in usual:
                pool = by_region[self.prov_idx.loc[t, "region"]]
                usual[t] = rng.choice(pool, 3, replace=False)
            r = str(rng.choice(usual[t], p=[.5, .3, .2]))
            out_ref[idx] = r
            ref_rows.append({"referring_provider_id": r, "target_provider_id": t, "target_facility_id": row.facility_id, "member_id": row.member_id,
                             "referral_date": max(row.service_date - pd.Timedelta(days=int(rng.integers(2, 14))), pd.Timestamp(config.DATA_START))})
        c.loc[list(out_ref), "referring_provider_id"] = pd.Series(out_ref)
        refs = pd.concat([pd.DataFrame(ref_rows)] + self.referral_frames, ignore_index=True)
        refs = refs.sort_values("referral_date").reset_index(drop=True)
        refs["referral_id"] = [f"REF-{i + 1:06d}" for i in range(len(refs))]
        self.referrals = refs
        self.claims = c

        # relationships: baseline associated_with (same-region, same practice group)
        regs = self.providers.groupby("region").provider_id.apply(list)
        for r, lst in regs.items():
            for _ in range(130):
                a, b = rng.choice(lst, 2, replace=False)
                self.add_assoc(str(a), str(b), config.DATA_START - timedelta(days=int(rng.integers(100, 2000))), "practice_group")
        rel = pd.DataFrame(self.relationships)
        rel["start_date"] = pd.to_datetime(rel["start_date"]).dt.date
        rel = rel.drop_duplicates(["entity_a_id", "entity_b_id", "relationship_type"]).reset_index(drop=True)
        rel["relationship_id"] = [f"REL-{i + 1:06d}" for i in range(len(rel))]
        self.relationship_df = rel
        self._investigations()

    def _investigations(self):
        rng = self.rng
        P = self.prov_idx
        rows = []
        pattern_text = {
            "R001_DUPLICATE": "repeated same-day billing of identical services for the same members",
            "R002_UPCODING": "an unusually high share of high-complexity visit codes relative to peers",
            "R003_UNBUNDLING": "panel components billed separately instead of the bundled code",
            "R004_IMPLAUSIBLE_SERVICE": "services inconsistent with member or facility context",
            "R005_EXCESSIVE_UTILIZATION": "claim volume far above comparable peers",
            "R006_IMPOSSIBLE_TIMING": "service volume or locations that could not be delivered in the time available",
            "R007_REFERRAL_CONCENTRATION": "referrals concentrated on a single partner provider",
            "R008_NETWORK_EXPANSION": "rapid growth in connected providers and facilities",
        }
        outcomes_hit = [("CONFIRMED_OVERPAYMENT", .55), ("DOCUMENTATION_REQUESTED", .20), ("MONITORED", .15), ("CLOSED_NO_ISSUE", .10)]
        outcomes_miss = [("CLOSED_NO_ISSUE", .55), ("MONITORED", .20), ("DOCUMENTATION_REQUESTED", .15), ("CONFIRMED_OVERPAYMENT", .10)]
        kindmap = {"duplicate": ["R001_DUPLICATE"], "upcoding": ["R002_UPCODING"], "excessive": ["R005_EXCESSIVE_UTILIZATION"],
                   "referral_concentration": ["R007_REFERRAL_CONCENTRATION"], "unbundling": ["R003_UNBUNDLING"]}

        def pick(opts):
            names, p = zip(*opts)
            return str(rng.choice(names, p=np.array(p) / sum(p)))

        def text(pid, pats, outcome, amount, extra=""):
            spec, reg = P.loc[pid].specialty, P.loc[pid].region
            clauses = "; ".join(pattern_text[x] for x in pats)
            tail = {"CONFIRMED_OVERPAYMENT": f"Review confirmed overpayment; ${amount:,.0f} identified for recovery.",
                    "DOCUMENTATION_REQUESTED": "Medical-record documentation was requested; follow-up review pending provider response.",
                    "MONITORED": "No conclusive finding; provider placed on monitoring with quarterly re-review.",
                    "CLOSED_NO_ISSUE": "Activity was explained by documented service mix; case closed without findings."}[outcome]
            return f"Investigation of {spec} provider {pid} ({reg}) opened after alerts for {clauses}. {extra}{tail}"

        # pinned similar case
        rows.append({"investigation_id": "INV-0087", "provider_id": "PRV-087", "opened_date": date(2025, 10, 20), "closed_date": date(2025, 12, 12),
                     "patterns": ["R001_DUPLICATE", "R007_REFERRAL_CONCENTRATION", "R008_NETWORK_EXPANSION"], "specialty": "Orthopedics", "outcome": "CONFIRMED_OVERPAYMENT",
                     "amount_identified": 412300.0,
                     "summary": ("Investigation of Orthopedics provider PRV-087 (SOUTH) opened after alerts for repeated same-day billing of identical services for the same members; "
                                 "referrals concentrated on a single partner provider; rapid growth in connected providers and facilities. A radiology and a physical therapy provider shared "
                                 "the same ambulatory surgery facility (FAC-030) and exchanged referrals with PRV-087. Review confirmed overpayment; $412,300 identified for recovery."),
                     "analyst_notes": "Shared-facility ring with PRV-088 and PRV-089; referral hub PRV-085 routed most inbound referrals to PRV-087. Documentation requested, then recovery referral."})
        n = 1
        used_inv = {"INV-0087"}
        hist = [("PRV-087", None)] + [(p, k) for p, k in self.hist_scenario_providers]
        for pid, kind in hist[1:]:
            pats = kindmap[kind]
            out = pick(outcomes_hit)
            amt = float(rng.uniform(20_000, 220_000)) if out == "CONFIRMED_OVERPAYMENT" else 0.0
            od = month_start(int(rng.integers(5, 9))) + timedelta(days=int(rng.integers(0, 25)))
            n += 1 if f"INV-{n:04d}" in used_inv or n == 87 else 0
            while f"INV-{n:04d}" in used_inv or n == 87:
                n += 1
            iid = f"INV-{n:04d}"
            used_inv.add(iid)
            rows.append({"investigation_id": iid, "provider_id": pid, "opened_date": od, "closed_date": od + timedelta(days=int(rng.integers(20, 80))), "patterns": pats,
                         "specialty": P.loc[pid].specialty, "outcome": out, "amount_identified": round(amt, 2), "summary": text(pid, pats, out, amt),
                         "analyst_notes": f"Pattern confirmed in claims history for {pid}." if out != "CLOSED_NO_ISSUE" else "Alert not substantiated."})
        allp = self.providers.provider_id.to_numpy()
        pool = [p for p in allp if p not in {x[0] for x in hist} and p not in {HERO, HUB, *CONTROLS, *RING_PARTNERS, *RING_B}]
        rng.shuffle(pool)
        k = 0
        while len(rows) < N_INVESTIGATIONS:
            pid = pool[k]
            k += 1
            npat = int(rng.integers(1, 3))
            pats = list(rng.choice(list(pattern_text), npat, replace=False))
            out = pick(outcomes_miss)
            amt = float(rng.uniform(5_000, 90_000)) if out == "CONFIRMED_OVERPAYMENT" else 0.0
            od = month_start(int(rng.integers(1, 10))) + timedelta(days=int(rng.integers(0, 25)))
            n += 1
            while f"INV-{n:04d}" in used_inv or n == 87:
                n += 1
            iid = f"INV-{n:04d}"
            used_inv.add(iid)
            rows.append({"investigation_id": iid, "provider_id": pid, "opened_date": od, "closed_date": od + timedelta(days=int(rng.integers(15, 90))), "patterns": pats,
                         "specialty": P.loc[pid].specialty, "outcome": out, "amount_identified": round(amt, 2), "summary": text(pid, pats, out, amt),
                         "analyst_notes": "Alert generated by prior screening; see summary."})
        inv = pd.DataFrame(rows)
        self.investigations = inv

    # ------------------------------------------------------------------ output
    def write(self, out: Path) -> dict:
        out.mkdir(parents=True, exist_ok=True)
        c = self.claims
        refmap = c.referring_provider_id
        claims_out = c[["claim_id", "member_id", "provider_id", "referring_provider_id", "facility_id", "service_date", "submit_date", "procedure_code",
                        "units", "billed_amount", "allowed_amount", "paid_amount", "service_minutes", "claim_type"]].copy()
        claims_out["service_date"] = claims_out.service_date.dt.date
        claims_out["submit_date"] = claims_out.submit_date.dt.date
        # planted invalid rows to prove ingestion validation/quarantine works
        bad = claims_out.sample(30, random_state=3).copy()
        bad["claim_id"] = [f"CLM-9{i:05d}" for i in range(len(bad))]
        bad.iloc[0:5, bad.columns.get_loc("paid_amount")] = -125.0
        bad.iloc[5:10, bad.columns.get_loc("member_id")] = ""
        bad.iloc[10:15, bad.columns.get_loc("provider_id")] = "PRV-9999"
        bad.iloc[15:20, bad.columns.get_loc("service_date")] = "2026-13-45"
        bad.iloc[20:25, bad.columns.get_loc("units")] = 0
        bad.iloc[25:30, bad.columns.get_loc("procedure_code")] = "XXXXX"
        claims_all = pd.concat([claims_out, bad], ignore_index=True)
        claims_all.to_csv(out / "claims.csv", index=False)
        c[["claim_id", "injected_fwa", "scenario"]].to_csv(out / "claim_labels.csv", index=False)
        self.facilities.to_csv(out / "facilities.csv", index=False)
        mem = self.members.copy()
        mem["death_date"] = pd.to_datetime(mem.death_date).dt.date
        mem.to_csv(out / "members.csv", index=False)
        self.providers.to_csv(out / "providers.csv", index=False)
        self.procedures.to_csv(out / "procedures.csv", index=False)
        refs = self.referrals.copy()
        refs["referral_date"] = pd.to_datetime(refs.referral_date).dt.date
        refs[["referral_id", "referring_provider_id", "target_provider_id", "target_facility_id", "member_id", "referral_date"]].to_csv(out / "referrals.csv", index=False)
        self.relationship_df[["relationship_id", "entity_a_type", "entity_a_id", "entity_b_type", "entity_b_id", "relationship_type", "start_date", "source"]].to_csv(out / "relationships.csv", index=False)
        inv = self.investigations.copy()
        inv["patterns"] = inv.patterns.apply(lambda x: "|".join(x))
        inv.to_csv(out / "investigations.csv", index=False)
        pl = []
        for pid in self.providers.provider_id:
            l = self.labels.get(pid, {"provider_id": pid, "role": "normal", "scenarios": [], "scenario_start": None, "notes": ""})
            pl.append({"provider_id": pid, "role": l["role"], "scenarios": "|".join(l["scenarios"]), "scenario_start": l["scenario_start"], "notes": l["notes"]})
        pd.DataFrame(pl).to_csv(out / "provider_labels.csv", index=False)
        summary = {
            "claims_valid": int(len(c)), "claims_planted_invalid": int(len(bad)), "injected_fwa_claims": int(c.injected_fwa.sum()),
            "providers": int(len(self.providers)), "members": int(len(self.members)), "facilities": int(len(self.facilities)),
            "referrals": int(len(self.referrals)), "relationships": int(len(self.relationship_df)), "investigations": int(len(self.investigations)),
            "scenario_provider_counts": {k: len(v) for k, v in self.scenario_providers.items()},
            "data_start": str(config.DATA_START), "data_end": str(config.DATA_END), "seed": config.SEED,
        }
        (out / "generation_summary.json").write_text(json.dumps(summary, indent=2))
        return summary


def generate(out_dir: Path | None = None) -> dict:
    out = Path(out_dir) if out_dir else config.SYNTH_DIR
    g = Generator()
    g.build_entities()
    g.build_baseline()
    g.inject_scenarios()
    g.finalize()
    return g.write(out)


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
