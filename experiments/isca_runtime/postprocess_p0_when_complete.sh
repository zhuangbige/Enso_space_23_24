#!/usr/bin/env bash
# Wait for the authoritative P0 pipeline gate, then summarize and package it.

set -euo pipefail

ROOT="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
ANALYSIS_PY="${ISCA_ANALYSIS_PY:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
RESULT_DIR="${ROOT}/results/p0_screening"
LOG="${ROOT}/logs/p0_postprocess.log"
LOCK="${ROOT}/logs/p0_postprocess.lock"

mkdir -p "${RESULT_DIR}" "${ROOT}/logs"
exec 8>"${LOCK}"
if ! flock -n 8; then
  printf '%s POSTPROCESS_ALREADY_RUNNING\n' "$(date -Is)" >> "${LOG}"
  exit 0
fi

log() {
  printf '%s %s\n' "$(date -Is)" "$*" | tee -a "${LOG}"
}

log "POSTPROCESS_WAIT_START"
while true; do
  if [[ -s "${RESULT_DIR}/pipeline_summary.txt" ]] && \
      grep -q '^P0_PIPELINE_COMPLETE' "${RESULT_DIR}/pipeline_summary.txt"; then
    break
  fi
  if ! pgrep -f '[a]lign_and_launch_p0.sh' >/dev/null; then
    log "POSTPROCESS_FAILED parent pipeline exited before a completion summary"
    exit 1
  fi
  sleep 60
done

log "POSTPROCESS_PIPELINE_GATE_FOUND"
"${ANALYSIS_PY}" "${ROOT}/summarize_isca_p0_results.py" \
  --input "${RESULT_DIR}" \
  --output "${RESULT_DIR}" >> "${LOG}" 2>&1
log "POSTPROCESS_SCIENTIFIC_SUMMARY_COMPLETE"

"${ROOT}/package_p0_key_artifacts.sh" "${ROOT}" >> "${LOG}" 2>&1
log "POSTPROCESS_PACKAGE_COMPLETE"

"${ANALYSIS_PY}" - "${RESULT_DIR}" <<'PY' >> "${LOG}" 2>&1
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
verification = json.loads((root / "p0_verification.json").read_text(encoding="utf-8"))
interpretation = json.loads(
    (root / "p0_scientific_interpretation.json").read_text(encoding="utf-8")
)
assert verification["complete"] is True
assert verification["valid_files"] == 240
assert verification["invalid_files"] == 0
assert verification["errors"] == []
assert (root / "p0_key_artifacts.tar.gz").stat().st_size > 0
print(
    "POSTPROCESS_FINAL_AUDIT_COMPLETE",
    "valid_files=240",
    f"strong_suppressive={interpretation['strong_suppressive_count']}/6",
)
PY

log "POSTPROCESS_P0_COMPLETE"
