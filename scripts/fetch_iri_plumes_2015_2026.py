"""Archive publicly displayed IRI vector plumes for the requested comparison."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/raw/iri_plumes_2015_2026_20261014'
OUT.mkdir(parents=True, exist_ok=True)


def fetch(item):
    name, url = item
    path = OUT / name
    if not path.exists():
        subprocess.run(['curl', '-fsSL', '--max-time', '60', '--retry', '2', url,
                        '-o', str(path) + '.partial'], check=True)
        Path(str(path) + '.partial').replace(path)
    data = path.read_bytes()
    if path.suffix == '.svg':
        assert b'<svg' in data and b'Model Predictions' in data
    return dict(file=name, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                retrieved_utc=datetime.now(timezone.utc).isoformat())


def main():
    for year in [2015, 2026]:
        cached = Path(f'/private/tmp/iri_plume_{year}_02.svg')
        if cached.exists():
            shutil.copyfile(cached, OUT / f'iri_plume_{year}_02.svg')
    tasks = [(f'iri_plume_{year}_{month:02}.svg',
              f'https://ensoforecast.iri.columbia.edu/figure4_plot/{year}/{month}')
             for year in [2015, 2026] for month in range(2, 7)]
    tasks += [(f'iri_{year}_June.html',
               f'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/{year}-June-quick-look/')
              for year in [2015, 2026]]
    tasks += [('iri_model_list.html', 'https://iri.columbia.edu/our-expertise/climate/enso/enso-prediction-models/')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, tasks))
    (OUT / 'source_manifest.json').write_text(json.dumps(results, indent=2))
    print(json.dumps([{'file': r['file'], 'bytes': r['bytes']} for r in results], indent=2))


if __name__ == '__main__':
    main()
