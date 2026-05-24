#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.experiments import seasonal_windows


def main() -> int:
    print("# First-Pass Diagnostic Checklist")
    print()
    print("1. Build monthly OISST and ERSST Nino-3/Nino-3.4 indices.")
    print("2. Build ERA5 equatorial Pacific u850 and SLP/SOI-like indices.")
    print("3. Fit historical SST-to-wind and SST-to-SOI regressions excluding target events.")
    print("4. Compute 2023/24 residuals relative to historical expected atmospheric response.")
    print("5. Compare precipitation and OLR response across ERA5, GPCP, and NOAA OLR.")
    print("6. Prepare seasonal anomaly maps for:")
    for label, months in seasonal_windows().items():
        print(f"   - {label}: months {', '.join(str(month) for month in months)}")
    print("7. Summarize 1982/83, 1997/98, 2015/16, and 2023/24 in the coupling-strength scatter plot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
