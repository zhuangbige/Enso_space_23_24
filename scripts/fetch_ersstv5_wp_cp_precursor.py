#!/usr/bin/env python3
"""Download the compact ERSSTv5 field needed for the Ludescher precursor.

The NCSS request contains monthly SST only over 5S-5N, 120E-150W.  The
1950-2025 interval is long enough to reproduce a 30-year trailing climatology
for every event year in the 1982-2023 SODA3 analysis.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/interim/research_2026/"
    "ersstv5_wp_cp_monthly_1950_2025.nc"
)
BASE = (
    "https://psl.noaa.gov/thredds/ncss/grid/"
    "Datasets/noaa.ersst.v5/sst.mnmean.nc"
)


def request_url() -> str:
    query = {
        "var": "sst",
        "north": 5,
        "west": 120,
        "east": 210,
        "south": -5,
        "time_start": "1950-12-01T00:00:00Z",
        "time_end": "2025-12-01T00:00:00Z",
        "timeStride": 12,
        "accept": "netcdf",
    }
    return f"{BASE}?{urlencode(query)}"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and OUTPUT.stat().st_size > 0:
        print(f"exists: {OUTPUT}")
        return 0
    temporary = OUTPUT.with_suffix(".nc.tmp")
    print(f"download: {OUTPUT}", flush=True)
    urlretrieve(request_url(), temporary)
    temporary.replace(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
