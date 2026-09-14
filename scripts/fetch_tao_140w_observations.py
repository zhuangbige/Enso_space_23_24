#!/usr/bin/env python3
"""Fetch compact TAO observations at 0N, 140W from NOAA PMEL ERDDAP."""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/tao_0n140w"
BASE = "https://data.pmel.noaa.gov/pmel/erddap/tabledap"


REQUESTS = {
    "tao_0n140w_daily_current.csv": (
        "pmelTaoDyCur",
        (
            "station,longitude,latitude,time,depth,U_320,V_321,"
            "QCS_5300,QCD_5310,SCS_6300,CIC_7300"
            "&longitude=220&latitude=0"
            "&time>=1980-01-01T00:00:00Z"
            "&time<=2026-06-30T23:59:59Z"
            "&depth<=300"
        ),
    ),
    "tao_0n140w_daily_adcp.csv": (
        "pmelTaoDyAdcp",
        (
            "station,longitude,latitude,time,depth,u_1205,QU_5205"
            "&longitude=220&latitude=0"
            "&time>=1988-01-01T00:00:00Z"
            "&time<=2026-06-30T23:59:59Z"
            "&depth<=300"
        ),
    ),
    "tao_0n140w_daily_d20.csv": (
        "pmelTaoDyIso",
        (
            "station,longitude,latitude,time,ISO_6,QI_5006"
            "&longitude=220&latitude=0"
            "&time>=1980-01-01T00:00:00Z"
            "&time<=2026-06-30T23:59:59Z"
        ),
    ),
    "tao_0n140w_daily_temperature.csv": (
        "pmelTaoDyT",
        (
            "station,longitude,latitude,time,depth,T_20,QT_5020,ST_6020"
            "&longitude=220&latitude=0"
            "&time>=1980-01-01T00:00:00Z"
            "&time<=2026-06-30T23:59:59Z"
            "&depth<=300"
        ),
    ),
}


def request_url(dataset: str, query: str) -> str:
    encoded = quote(query, safe=",&=-:")
    return f"{BASE}/{dataset}.csv?{encoded}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, (dataset, query) in REQUESTS.items():
        target = OUT / filename
        if target.exists() and target.stat().st_size > 0:
            print(f"exists: {target}")
            continue
        temporary = target.with_suffix(".csv.tmp")
        print(f"download: {target}", flush=True)
        try:
            urlretrieve(request_url(dataset, query), temporary)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"ERDDAP request failed for {dataset}: {detail}"
            ) from error
        temporary.replace(target)
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
