#!/usr/bin/env python3
"""Fetch compact GODAS slices for published ENSO recharge diagnostics.

The requested domains are not tuned to 2026.  They are fixed by the
published definitions used later in the analysis:

* WWV: 5S-5N, 120E-80W (Meinen and McPhaden, 2000);
* zonal warm-water transport: 170E, 10S-5N;
* meridional warm-water transport: 5N and 10S, 140E-80W
  (Chakravorty et al., 2021, their Fig. 8).

Only January-June is downloaded for the official NOAA/CPC RONI event years
and 2026.  The 1991-2020 monthly long-term means are downloaded once for
same-calendar-month anomalies.
"""

from __future__ import annotations

import argparse
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/godas/authoritative_recharge_sections"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2009, 2015, 2023, 2026)
BASE = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/godas"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--climatology-only", action="store_true")
    return parser.parse_args()


def request_url(
    dataset: str,
    variable: str,
    bounds: tuple[float, float, float, float],
    *,
    year: int | None = None,
    climatology: bool = False,
) -> str:
    west, east, south, north = bounds
    params: list[tuple[str, str]] = [
        ("var", variable),
        ("north", str(north)),
        ("west", str(west)),
        ("east", str(east)),
        ("south", str(south)),
        ("disableProjSubset", "on"),
        ("horizStride", "1"),
    ]
    if year is not None:
        params.extend(
            [
                ("time_start", f"{year}-01-01T00:00:00Z"),
                ("time_end", f"{year}-06-01T00:00:00Z"),
                ("timeStride", "1"),
            ]
        )
    elif climatology:
        params.extend(
            [
                ("time_start", "0001-01-01T00:00:00Z"),
                ("time_end", "0001-12-01T00:00:00Z"),
                ("timeStride", "1"),
            ]
        )
    params.append(("accept", "netcdf4"))
    return f"{BASE}/{dataset}?{urllib.parse.urlencode(params)}"


def download(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and destination.stat().st_size > 4096 and not force:
        print(f"keep {destination.name} ({destination.stat().st_size / 1024:.0f} KiB)")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    headers = {"User-Agent": "Mozilla/5.0 (ENSO recharge research; NOAA PSL NCSS)"}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=240) as response:
                data = response.read()
            if len(data) < 4096 or data[:4] not in (b"\x89HDF", b"CDF\x01", b"CDF\x02"):
                raise RuntimeError(f"unexpected response ({len(data)} bytes): {data[:160]!r}")
            temporary.write_bytes(data)
            temporary.replace(destination)
            print(f"saved {destination.name} ({len(data) / 1024:.0f} KiB)")
            return
        except Exception as error:  # network retries are intentional here
            last_error = error
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to download {destination.name}: {last_error}")


def main() -> None:
    args = parse_args()
    fields = {
        # broad temperature subset supports exact WWV and temperatures at all
        # three transport sections.
        "pottmp": ("pottmp", (119.8, 280.2, -10.4, 5.4)),
        # narrow velocity sections minimize the transfer size.
        "ucur_170e": ("ucur", (169.5, 170.5, -10.4, 5.4)),
        "vcur_5n": ("vcur", (139.8, 280.2, 4.8, 5.2)),
        "vcur_10s": ("vcur", (139.8, 280.2, -10.2, -9.8)),
    }
    if not args.climatology_only:
        for year in EVENT_YEARS:
            for label, (variable, bounds) in fields.items():
                dataset = f"{variable}.{year}.nc"
                destination = OUT / f"godas_{label}_{year}_jan_jun.nc"
                download(
                    request_url(dataset, variable, bounds, year=year),
                    destination,
                    args.force,
                )

    for label, (variable, bounds) in fields.items():
        dataset = f"Derived/{variable}.mon.ltm.1991-2020.nc"
        destination = OUT / f"godas_{label}_climatology_1991_2020.nc"
        download(
            request_url(dataset, variable, bounds, climatology=True),
            destination,
            args.force,
        )


if __name__ == "__main__":
    main()
