#!/usr/bin/env bash
set -uo pipefail

RUNTIME="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
ANALYSIS_PY="${ISCA_ANALYSIS_PY:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
PRICE_PER_HOUR="${PRICE_PER_HOUR:-1.77}"
LOG_DIR="${RUNTIME}/logs"
RESULT_DIR="${RUNTIME}/results/p0_screening"
FIGURE_DIR="${RESULT_DIR}/figures"
PIPELINE_LOG="${LOG_DIR}/align_and_launch_p0.log"
ALIGN_LOG="${LOG_DIR}/march_aligned_pool_master.log"
PARALLEL_LOG="${LOG_DIR}/parallel_6_benchmark_master.log"
P0_LOG="${LOG_DIR}/p0_screening_master.log"
LOCK_FILE="${LOG_DIR}/align_and_launch_p0.lock"

mkdir -p "${LOG_DIR}" "${RESULT_DIR}" "${FIGURE_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "ALIGN_PIPELINE_ALREADY_RUNNING $(date -Is)" >> "${PIPELINE_LOG}"
  exit 0
fi

log() {
  echo "$(date -Is) $*" | tee -a "${PIPELINE_LOG}"
}

log "ALIGN_PIPELINE_START waiting_for_parallel_benchmark"
while pgrep -f '[b]enchmark_parallel_6.sh' >/dev/null; do
  sleep 60
done

if ! grep -q 'PARALLEL_BENCHMARK_COMPLETE' "${PARALLEL_LOG}"; then
  log "ALIGN_PIPELINE_FAILED existing parallel benchmark did not complete"
  exit 1
fi
if ! "${ANALYSIS_PY}" -c \
    "import json; d=json.load(open('${RESULT_DIR}/parallel_benchmark_validation.json')); assert d['complete'] and d['valid_jobs']==6"; then
  log "ALIGN_PIPELINE_FAILED parallel benchmark scientific audit"
  exit 1
fi
log "ALIGN_PIPELINE_PARALLEL_BENCHMARK_VALIDATED"

if ! "${ANALYSIS_PY}" -c \
    "import json; d=json.load(open('${RESULT_DIR}/factorial_sst_validation.json')); assert d['complete'] and not d['errors']"; then
  log "ALIGN_PIPELINE_FAILED factorial SST audit"
  exit 1
fi
log "ALIGN_PIPELINE_SST_VALIDATED"

if "${ANALYSIS_PY}" -c \
    "import json; d=json.load(open('${RESULT_DIR}/march_aligned_pool_validation.json')); assert d['complete'] and d['unique_state_hashes']==10" \
    2>/dev/null; then
  log "ALIGN_PIPELINE_MARCH_POOL_ALREADY_VALIDATED"
else
  if ! MAX_PARALLEL=6 bash "${RUNTIME}/generate_march_aligned_ensemble.sh" \
      > "${ALIGN_LOG}" 2>&1; then
    log "ALIGN_PIPELINE_FAILED March-aligned restart generation"
    exit 1
  fi
  if ! "${ANALYSIS_PY}" "${RUNTIME}/validate_march_aligned_restart_pool.py" \
      --data "${RUNTIME}/data" \
      --members 10 \
      --output "${RESULT_DIR}/march_aligned_pool_validation.json" \
      >> "${PIPELINE_LOG}" 2>&1; then
    log "ALIGN_PIPELINE_FAILED March-aligned restart validation"
    exit 1
  fi
  log "ALIGN_PIPELINE_MARCH_POOL_VALIDATED"
fi

parallel_wall=$(sed -n \
  's/.*PARALLEL_BENCHMARK_COMPLETE.*wall_seconds=\([0-9][0-9]*\).*/\1/p' \
  "${PARALLEL_LOG}" | tail -1)
if [[ -z "${parallel_wall}" || "${parallel_wall}" -le 0 ]]; then
  log "ALIGN_PIPELINE_FAILED cannot parse parallel benchmark wall time"
  exit 1
fi
speedup=$(awk -v baseline="858.212667" -v wall="${parallel_wall}" \
  'BEGIN {printf "%.3f", 6.0 * baseline / wall}')
if awk -v value="${speedup}" 'BEGIN {exit !(value >= 4.5)}'; then
  selected_parallel=6
elif awk -v value="${speedup}" 'BEGIN {exit !(value >= 3.0)}'; then
  selected_parallel=4
else
  selected_parallel=2
fi
log "ALIGN_PIPELINE_CONCURRENCY wall_seconds=${parallel_wall} speedup=${speedup} selected_parallel=${selected_parallel}"

if grep -q 'P0_SCREENING_COMPLETE' "${P0_LOG}" 2>/dev/null; then
  log "ALIGN_PIPELINE_P0_ALREADY_COMPLETE"
else
  if ! MAX_PARALLEL="${selected_parallel}" \
      bash "${RUNTIME}/run_p0_screening.sh" > "${P0_LOG}" 2>&1; then
    log "ALIGN_PIPELINE_FAILED P0 production matrix"
    exit 1
  fi
  log "ALIGN_PIPELINE_P0_RUN_COMPLETE"
fi

if ! "${ANALYSIS_PY}" "${RUNTIME}/verify_and_summarize_p0.py" \
    --data "${RUNTIME}/data" \
    --output "${RESULT_DIR}" \
    --members 10 \
    --months 6 \
    >> "${PIPELINE_LOG}" 2>&1; then
  log "ALIGN_PIPELINE_FAILED P0 full verification"
  exit 1
fi
log "ALIGN_PIPELINE_P0_VERIFIED"

mkdir -p /root/autodl-tmp/p0_mplconfig
if ! MPLCONFIGDIR=/root/autodl-tmp/p0_mplconfig \
    "${ANALYSIS_PY}" "${RUNTIME}/plot_p0_screening_results.py" \
      --input "${RESULT_DIR}" \
      --output "${FIGURE_DIR}" \
      >> "${PIPELINE_LOG}" 2>&1; then
  log "ALIGN_PIPELINE_FAILED P0 figure generation"
  exit 1
fi
log "ALIGN_PIPELINE_P0_FIGURES_COMPLETE"

alignment_wall=$(sed -n \
  's/.*MARCH_ALIGNED_POOL_COMPLETE.*wall_seconds=\([0-9][0-9]*\).*/\1/p' \
  "${ALIGN_LOG}" | tail -1)
p0_wall=$(sed -n \
  's/.*P0_SCREENING_COMPLETE.*wall_seconds=\([0-9][0-9]*\).*/\1/p' \
  "${P0_LOG}" | tail -1)
alignment_cost=$(awk -v seconds="${alignment_wall:-0}" -v price="${PRICE_PER_HOUR}" \
  'BEGIN {printf "%.2f", seconds / 3600.0 * price}')
p0_cost=$(awk -v seconds="${p0_wall:-0}" -v price="${PRICE_PER_HOUR}" \
  'BEGIN {printf "%.2f", seconds / 3600.0 * price}')

{
  echo "P0_PIPELINE_COMPLETE $(date -Is)"
  echo "parallel_benchmark_wall_seconds=${parallel_wall}"
  echo "parallel_speedup=${speedup}"
  echo "selected_parallel=${selected_parallel}"
  echo "march_alignment_wall_seconds=${alignment_wall:-unknown}"
  echo "march_alignment_cost_cny=${alignment_cost}"
  echo "p0_wall_seconds=${p0_wall:-unknown}"
  echo "p0_wall_cost_cny=${p0_cost}"
  echo "price_per_hour_cny=${PRICE_PER_HOUR}"
  echo "result_dir=${RESULT_DIR}"
} > "${RESULT_DIR}/pipeline_summary.txt"
log "P0_PIPELINE_COMPLETE alignment_wall=${alignment_wall:-unknown} p0_wall=${p0_wall:-unknown}"
