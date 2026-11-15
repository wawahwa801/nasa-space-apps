"""Build fire-dashboard/data/reference-data.js from the NASA files in data/.

Run from the repository root:

    python fire-dashboard/scripts/build_reference_data.py

Uses only the Python standard library. The output is a JavaScript file (not
JSON) so the dashboard can be opened directly from disk without a web server.
Re-run it whenever a file in data/ changes.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = REPO / "fire-dashboard" / "data" / "reference-data.js"

ACME_FILE = "PSI-159_Raw Data_Final ACME Chamber Calculator - 2021-03-09 to 2021-10-21.xlsx"
SAFFIRE_FILE = "Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx"
SPICE_FILE = "PSI-107_Experimental table_Spice.csv"
SAMER_FILE = "PSI-101_Experimental table_SAME-R.csv"
BASS2_FILE = "BASS-II Test Matrix by PI Final.xlsx"
BASS1_FILE = "PSI-26_Experimental table_BASS.csv"

PSI_TO_KPA = 6.894757
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


# --- minimal .xlsx reader -------------------------------------------------


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    out = []
    for _ev, el in ET.iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == M + "si":
            out.append("".join(t.text or "" for t in el.iter(M + "t")))
            el.clear()
    return out


def _sheet_path(z: zipfile.ZipFile, name: str) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels}
    for sheet in wb.iter(M + "sheet"):
        if sheet.get("name") == name:
            target = targets[sheet.get(R + "id")].lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise KeyError(f"sheet '{name}' not found")


def iter_rows(path: Path, sheet: str):
    """Yield (row_number, {column_index: text}) for one sheet, streaming."""
    with zipfile.ZipFile(path) as z:
        shared = _shared_strings(z)
        for _ev, el in ET.iterparse(z.open(_sheet_path(z, sheet))):
            if el.tag != M + "row":
                continue
            values = {}
            for c in el.findall(M + "c"):
                v = c.find(M + "v")
                text = v.text if v is not None else None
                if text is not None and c.get("t") == "s":
                    text = shared[int(text)]
                if text not in (None, ""):
                    values[_col_index(c.get("r"))] = text
            yield int(el.get("r")), values
            el.clear()


def num(value) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def rnd(x: float | None, digits: int = 3) -> float | None:
    return None if x is None else round(x, digits)


# --- ACME (PSI-159) -------------------------------------------------------

# EventData columns (0-based), from the sheet's header rows 2-4.
ACME_COLS = {
    "op": 0, "ignite": 1, "tpid": 2, "t_start": 12, "p_start_psia": 18, "p_end_psia": 19,
    "type": 22, "fuel": 23, "burn_fraction": 37,
}
# "Finish Mixture (Percent)" block: fractions of the chamber gas after the event.
ACME_MIX = {
    "o2": 75, "he": 76, "co2": 77, "n2": 78, "h2o": 79,
    "ethylene": 80, "methane": 81, "propane": 82, "butane": 83, "ethane": 84, "h2": 85,
}
FUEL_SPECIES = ("ethylene", "methane", "propane", "butane", "ethane", "h2")


def build_acme() -> dict:
    tests = []
    for row, v in iter_rows(DATA / ACME_FILE, "EventData"):
        if row < 5 or v.get(ACME_COLS["op"]) != "TP":
            continue
        ignite = v.get(ACME_COLS["ignite"])
        if ignite not in ("Yes", "No"):
            continue
        mix = {k: num(v.get(c)) for k, c in ACME_MIX.items()}
        if mix["o2"] is None:
            continue
        p_end = num(v.get(ACME_COLS["p_end_psia"]))
        p_start = num(v.get(ACME_COLS["p_start_psia"]))
        fuel_frac = sum(mix[s] or 0 for s in FUEL_SPECIES)
        tests.append({
            "id": v.get(ACME_COLS["tpid"]),
            "date": (v.get(ACME_COLS["t_start"]) or "")[:10],
            "fuel": v.get(ACME_COLS["fuel"]) or "Unspecified",
            "ignited": ignite == "Yes",
            "o2_pct": rnd(mix["o2"] * 100, 2),
            "n2_pct": rnd((mix["n2"] or 0) * 100, 2),
            "co2_pct": rnd((mix["co2"] or 0) * 100, 3),
            "he_pct": rnd((mix["he"] or 0) * 100, 2),
            "fuel_pct": rnd(fuel_frac * 100, 3),
            "pressure_kpa": rnd(p_end * PSI_TO_KPA, 2) if p_end is not None else None,
            "pressure_start_kpa": rnd(p_start * PSI_TO_KPA, 2) if p_start is not None else None,
        })
    return {
        "name": "ACME chamber tests (PSI-159)",
        "file": ACME_FILE,
        "description": (
            "Test points from the ACME Chamber Calculator 'EventData' sheet, ISS, "
            "2021-03-09 to 2021-10-21. Composition is the calculator's 'Finish Mixture "
            "(Percent)'; pressure is the chamber pressure at the end of the test point "
            "(FCU_MP_PT28, converted from psia). 'Ignited' is the as-run Yes/No decision."
        ),
        "tests": tests,
    }


# --- Saffire-I sample 2 ---------------------------------------------------

SAFFIRE_COLS = {
    "t": 0, "epoch_ms": 1, "co2_pct": 5, "o2_pct": 6, "flow_cm_s": 7, "pressure_psia": 9,
    "humidity_pct": 22, "inlet_temp_c": 23,
}
PLUME_TC = range(24, 30)
SAMPLE_TC = range(30, 36)
SAFFIRE_BIN_S = 2.0


def build_saffire() -> dict:
    bins: dict[int, dict[str, list[float]]] = {}
    start_epoch = None
    for row, v in iter_rows(DATA / SAFFIRE_FILE, "Calibrated Data"):
        if row < 3:
            continue
        t = num(v.get(SAFFIRE_COLS["t"]))
        epoch = num(v.get(SAFFIRE_COLS["epoch_ms"]))
        if t is None or epoch is None:  # rows after the sensor log hold a separate block
            continue
        if start_epoch is None:
            start_epoch = epoch
        b = bins.setdefault(int(t // SAFFIRE_BIN_S), {})
        for key, c in SAFFIRE_COLS.items():
            if key in ("t", "epoch_ms"):
                continue
            x = num(v.get(c))
            if x is not None:
                b.setdefault(key, []).append(x)
        for key, cols in (("plume_max_c", PLUME_TC), ("sample_max_c", SAMPLE_TC)):
            temps = [x for x in (num(v.get(c)) for c in cols) if x is not None]
            if temps:
                b.setdefault(key, []).append(max(temps))

    keys = list(SAFFIRE_COLS)[2:] + ["plume_max_c", "sample_max_c"]
    series = {"t_s": []} | {k: [] for k in keys}
    for idx in sorted(bins):
        b = bins[idx]
        series["t_s"].append(rnd(idx * SAFFIRE_BIN_S, 1))
        for k in keys:
            vals = b.get(k)
            if k == "pressure_psia":
                mean = sum(vals) / len(vals) * PSI_TO_KPA if vals else None
            elif k in ("plume_max_c", "sample_max_c"):
                mean = max(vals) if vals else None
            else:
                mean = sum(vals) / len(vals) if vals else None
            series[k].append(rnd(mean, 3))
    series["pressure_kpa"] = series.pop("pressure_psia")
    start = (
        datetime.fromtimestamp(start_epoch / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if start_epoch
        else None
    )
    return {
        "name": "Saffire-I sample 2 sensor log",
        "file": SAFFIRE_FILE,
        "description": (
            f"'Calibrated Data' sheet, starting {start}. Averaged into {SAFFIRE_BIN_S:g}-second "
            "bins (temperatures: the hottest reading in each bin across thermocouples TC1-6 "
            "for plume and TC7-12 for sample). Pressure converted from psia."
        ),
        "bin_seconds": SAFFIRE_BIN_S,
        "series": series,
        "units": {
            "co2_pct": "%", "o2_pct": "%", "flow_cm_s": "cm/s", "pressure_kpa": "kPa",
            "humidity_pct": "%", "inlet_temp_c": "°C", "plume_max_c": "°C", "sample_max_c": "°C",
        },
    }


# --- SPICE (PSI-107) and SAME-R (PSI-101) CSVs -----------------------------


def read_csv(name: str) -> list[dict[str, str]]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(f)]


def build_spice() -> dict:
    runs = []
    for r in read_csv(SPICE_FILE):
        fuel_rate = num(r.get("Fuel Rate (mg/s)"))
        if not r.get("Fuel") or fuel_rate is None:
            continue
        runs.append({
            "day_of_year": r.get("GMT date"),
            "fuel": r["Fuel"],
            "nozzle_mm": rnd(num(r.get("Nozzle (mm)")), 4),
            "fuel_rate_mg_s": rnd(fuel_rate, 3),
            "air_rate_cm_s": rnd(num(r.get("Air Rate (cm/s)")), 2),
        })
    return {
        "name": "SPICE gas-jet flame runs (PSI-107)",
        "file": SPICE_FILE,
        "description": "Laminar gas-jet flames in coflowing air: fuel, nozzle diameter, fuel and air flow rates.",
        "runs": runs,
    }


def build_samer() -> dict:
    tests = []
    for r in read_csv(SAMER_FILE):
        if not r.get("Sample Type"):
            continue
        tests.append({
            "material": r["Sample Type"],
            "test": r.get("SAME Test #"),
            "description": r.get("Description"),
            "inlet_velocity_cm_s": num(r.get("Inlet velocity (cm/s)")),
            "heater_ratio": num(r.get("Rt/R0")),
            "duration_s": num(r.get("Duration (sec)")),
            "net_aging_s": num(r.get("Net aging time (sec)")),
        })
    return {
        "name": "SAME-R smoke tests (PSI-101)",
        "file": SAMER_FILE,
        "description": (
            "Smoke produced by heating spacecraft materials. Rt/R0 is the heated wire's "
            "resistance ratio (higher = hotter); net aging time is how long smoke aged before measurement."
        ),
        "tests": tests,
    }


# --- BASS-II (2014-2016) and BASS (2012-2013) solid-fuel burns ---------------


def sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        return [sh.get("name") for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(M + "sheet")]


def material_category(text: str) -> str:
    """Group the free-text sample descriptions. PMMA rods, films, slabs and
    spheres are all acrylic; "clear"/"black" rods in BASS-II are PMMA rods."""
    t = (text or "").lower()
    if "sibal" in t:
        return "SIBAL fabric (cotton-fiberglass)"
    if "nomex" in t:
        return "Nomex"
    if "ultem" in t:
        return "Ultem"
    if "wax" in t or "candle" in t or "paraf" in t or "parraf" in t:
        return "Wax (candle or slab)"
    if any(k in t for k in ("pmma", "rod", "film", "micron", "sphere", "spherical", "slab")):
        return "PMMA (acrylic)"
    return "Other"


def excel_date(value) -> str | None:
    x = num(value)
    if x is None:
        return None
    return (datetime(1899, 12, 30) + timedelta(days=x)).strftime("%Y-%m-%d")


def clean(value) -> str:
    return " ".join(str(value or "").split())


# BASS-II columns (0-based), identical on every PI sheet.
BASS2_COLS = {
    "date": 0, "gmt_day": 1, "test": 2, "sample": 3, "material": 4, "flow_restrictor": 5,
    "fan_display": 6, "air_display": 7, "o2_initial": 10, "o2_final": 11,
    "co2_initial": 12, "co2_final": 13, "co_initial": 14, "co_final": 15,
}


def build_bass() -> dict:
    tests = []
    path = DATA / BASS2_FILE
    for pi in sheet_names(path):
        for row, v in iter_rows(path, pi):
            if row < 2 or not v.get(BASS2_COLS["test"]):
                continue
            get = lambda k: v.get(BASS2_COLS[k])
            co_i, co_f = num(get("co_initial")), num(get("co_final"))
            co2_i, co2_f = num(get("co2_initial")), num(get("co2_final"))
            tests.append({
                "pi": pi,
                "test": clean(get("test")),
                "date": excel_date(get("date")),
                "material": clean(get("material")),
                "category": material_category(get("material")),
                "o2_initial_pct": rnd(num(get("o2_initial")), 2),
                "o2_final_pct": rnd(num(get("o2_final")), 2),
                "co2_initial_pct": rnd(co2_i, 3),
                "co2_final_pct": rnd(co2_f, 3),
                "co_initial_ppm": co_i,
                "co_final_ppm": co_f,
                # Raw text kept where the sheet holds notes instead of numbers (e.g. ">500", "OR").
                "co_final_raw": clean(get("co_final")),
                "co_rise_ppm": rnd(co_f - co_i, 1) if co_i is not None and co_f is not None else None,
                "co2_rise_pct": rnd(co2_f - co2_i, 3) if co2_i is not None and co2_f is not None else None,
                "air_display": clean(get("air_display")),
            })

    runs = []
    for r in read_csv(BASS1_FILE):
        test = r.get("Test #", "")
        material = r.get("Fuel Sample Material", "")
        if not test or not material:
            continue  # e.g. "SOOT Cleaning" maintenance rows
        text = material.lower()
        runs.append({
            "date": r.get("Date"),
            "test": test,
            "sample": r.get("Sample #"),
            "material": clean(material),
            "category": material_category(material),
            "configuration": "opposed flow" if ("opposed" in text or "oppsed" in text)
            else "wake ignition" if "wake" in text else "",
        })

    return {
        "name": "BASS-II solid-fuel burns (ISS, 2014-2016)",
        "file": BASS2_FILE,
        "description": (
            "Test matrix from the six BASS-II investigator sheets: sample material, calibrated chamber O₂ "
            "at the start and end of each test, CO₂ (%) and CO (ppm) before and after, and the air-flow "
            "display as recorded. Outcomes (ignition, extinction) are not recorded as columns."
        ),
        "tests": tests,
        "bass1": {
            "name": "BASS run log (ISS, 2012-2013, PSI-26)",
            "file": BASS1_FILE,
            "description": "As-run test list with sample material only; no atmosphere or flow conditions.",
            "runs": runs,
        },
    }


def main() -> int:
    missing = [f for f in (ACME_FILE, SAFFIRE_FILE, SPICE_FILE, SAMER_FILE, BASS2_FILE, BASS1_FILE) if not (DATA / f).exists()]
    if missing:
        print("Missing data files: " + ", ".join(missing), file=sys.stderr)
        return 1
    ref = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "acme": build_acme(),
        "saffire": build_saffire(),
        "spice": build_spice(),
        "samer": build_samer(),
        "bass": build_bass(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(ref, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(
        "// Generated by fire-dashboard/scripts/build_reference_data.py from data/. Do not edit by hand.\n"
        f"window.REFERENCE_DATA = {body};\n",
        encoding="utf-8",
    )
    acme = ref["acme"]["tests"]
    print(f"ACME: {len(acme)} test points ({sum(t['ignited'] for t in acme)} ignited)")
    print(f"Saffire: {len(ref['saffire']['series']['t_s'])} bins")
    print(f"SPICE: {len(ref['spice']['runs'])} runs; SAME-R: {len(ref['samer']['tests'])} tests")
    bass = ref["bass"]
    print(f"BASS-II: {len(bass['tests'])} tests; BASS: {len(bass['bass1']['runs'])} runs")
    print(f"Wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
