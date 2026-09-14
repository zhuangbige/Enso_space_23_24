#!/usr/bin/env bash
# Package the compact, audit-complete P0 record without duplicating raw NetCDF.

set -euo pipefail

ROOT="${1:-/root/autodl-tmp/isca_runtime}"
PYTHON_BIN="${PYTHON_BIN:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
RESULT_DIR="${ROOT}/results/p0_screening"
VERIFY_JSON="${RESULT_DIR}/p0_verification.json"
ARCHIVE="${RESULT_DIR}/p0_key_artifacts.tar.gz"
STAGE="$(mktemp -d "${ROOT}/p0_package.XXXXXX")"
trap 'rm -rf "${STAGE}"' EXIT

"${PYTHON_BIN}" - "${VERIFY_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"missing verification file: {path}")
audit = json.loads(path.read_text(encoding="utf-8"))
required = {
    "complete": True,
    "expected_files": 240,
    "valid_files": 240,
    "invalid_files": 0,
}
wrong = {key: (audit.get(key), value) for key, value in required.items() if audit.get(key) != value}
if wrong or audit.get("errors"):
    raise SystemExit(f"P0 audit is not complete: wrong={wrong}, errors={audit.get('errors')}")
PY

mkdir -p "${STAGE}/results/p0_screening/figures" "${STAGE}/logs" "${STAGE}/scripts"

required_results=(
  p0_verification.json
  p0_monthly_metrics.csv
  p0_paired_monthly_effects.csv
  p0_mjj_factorial_summary.csv
  p0_mjj_factorial_summary_oriented.csv
  p0_scientific_interpretation.json
  p0_scientific_interpretation.md
  pipeline_summary.txt
  factorial_sst_validation.json
  ensemble_restart_pool_validation.json
  march_aligned_pool_validation.json
  parallel_benchmark_validation.json
)

for name in "${required_results[@]}"; do
  source_path="${RESULT_DIR}/${name}"
  if [[ ! -s "${source_path}" ]]; then
    echo "missing required package artifact: ${source_path}" >&2
    exit 1
  fi
  cp "${source_path}" "${STAGE}/results/p0_screening/${name}"
done

for name in benchmark_6months_validation.json; do
  source_path="${ROOT}/logs/${name}"
  if [[ ! -s "${source_path}" ]]; then
    echo "missing required package log artifact: ${source_path}" >&2
    exit 1
  fi
  cp "${source_path}" "${STAGE}/logs/${name}"
done

for name in \
  fig_p0_monthly_paired_response.png \
  fig_p0_monthly_paired_response.pdf \
  fig_p0_mjj_factorial_effects.png \
  fig_p0_mjj_factorial_effects.pdf; do
  source_path="${RESULT_DIR}/figures/${name}"
  if [[ ! -s "${source_path}" ]]; then
    echo "missing required package figure: ${source_path}" >&2
    exit 1
  fi
  cp "${source_path}" "${STAGE}/results/p0_screening/figures/${name}"
done

for name in \
  align_and_launch_p0.log \
  march_aligned_pool_master.log \
  p0_screening_master.log \
  parallel_6_benchmark_master.log \
  benchmark_6months.log; do
  source_path="${ROOT}/logs/${name}"
  if [[ -s "${source_path}" ]]; then
    cp "${source_path}" "${STAGE}/logs/${name}"
  fi
done

for name in \
  run_2023_factorial.py \
  run_p0_screening.sh \
  verify_and_summarize_p0.py \
  summarize_isca_p0_results.py \
  plot_p0_screening_results.py \
  generate_march_aligned_ensemble.sh \
  run_control_member_to_march.py \
  validate_march_aligned_restart_pool.py \
  align_and_launch_p0.sh; do
  cp "${ROOT}/${name}" "${STAGE}/scripts/${name}"
done

(
  cd "${STAGE}"
  find . -type f ! -name MANIFEST.sha256 -print0 \
    | sort -z \
    | xargs -0 sha256sum > MANIFEST.sha256
)

tar -C "${STAGE}" -czf "${ARCHIVE}" .
sha256sum "${ARCHIVE}" > "${ARCHIVE}.sha256"
echo "P0_PACKAGE_COMPLETE archive=${ARCHIVE}"
