"""Download official 2023 February--June IRI vector plumes with provenance."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import fetch_iri_plumes_2015_2026 as archive

ROOT=Path(__file__).resolve().parents[1]


def main():
    archive.OUT=ROOT/'data/raw/iri_plumes_2023_20261014'
    archive.OUT.mkdir(parents=True,exist_ok=True)
    manifest=archive.OUT/'source_manifest.json'
    if manifest.exists():
        existing=json.loads(manifest.read_text())
        if all((archive.OUT/r['file']).exists() for r in existing):
            print('Archived source files already present; retaining original retrieval timestamps.')
            return
    tasks=[(f'iri_plume_2023_{m:02}.svg',f'https://ensoforecast.iri.columbia.edu/figure4_plot/2023/{m}')
           for m in range(2,7)]
    tasks.append(('iri_2023_June.html','https://iri.columbia.edu/our-expertise/climate/forecasts/enso/2023-June-quick-look/'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(archive.fetch,tasks))
    manifest.write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
