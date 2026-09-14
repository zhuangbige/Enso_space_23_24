#!/usr/bin/env bash
set -uo pipefail

RUNTIME="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
ANALYSIS_PY="${ISCA_ANALYSIS_PY:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
PRICE_PER_HOUR="${PRICE_PER_HOUR:-1.77}"
POOL_EXP="${RUNTIME}/data/isca_control_ensemble_pool_t42"
LOG_DIR="${RUNTIME}/logs"
RESULT_DIR="${RUNTIME}/results/p0_screening"
FIGURE_DIR="${RESULT_DIR}/figures"
GATE_LOG="${LOG_DIR}/gate_and_launch_p0.log"
PARALLEL_LOG="${LOG_DIR}/parallel_6_benchmark_master.log"
P0_LOG="${LOG_DIR}/p0_screening_master.log"
LOCK_FILE="${LOG_DIR}/gate_and_launch_p0.lock"

mkdir -p "${LOG_DIR}" "${RESULT_DIR}" "${FIGURE_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "GATE_ALREADY_RUNNING $(date -Is)" >> "${GATE_LOG}"
  exit 0
fi

log() {
  echo "$(date -Is) $*" | tee -a "${GATE_LOG}"
}

log "GATE_START waiting_for_control_pool"
while pgrep -f '[g]enerate_control_ensemble_restarts.py' >/dev/null; do
  sleep 60
done

if ! grep -q 'CONTROL_ENSEMBLE_POOL_COMPLETE members=10' "${LOG_DIR}/control_ensemble_pool.log"; then
  log "GATE_FAILED control pool exited without completion marker"
  exit 1
fi
log "GATE_POOL_PROCESS_COMPLETE"

if ! "${ANALYSIS_PY}" "${RUNTIME}/validate_ensemble_restart_pool.py" \
    --experiment "${POOL_EXP}" \
    --members 10 \
    --output "${RESULT_DIR}/ensemble_restart_pool_validation.json" \
    >> "${GATE_LOG}" 2>&1; then
  log "GATE_FAILED ensemble restart pool validation"
  exit 1
fi
log "GATE_POOL_VALIDATED"

if ! "${ANALYSIS_PY}" -c \
    "import json; d=json.load(open('${LOG_DIR}/benchmark_6months_validation.json')); assert d['complete'] and d['valid_monthly_files']==6 and d['valid_restarts']==6"; then
  log "GATE_FAILED six-month benchmark audit is absent or incomplete"
  exit 1
fi
log "GATE_BENCHMARK_VALIDATED"

if grep -q 'P0_SCREENING_COMPLETE' "${P0_LOG}" 2>/dev/null; then
  log "GATE_P0_ALREADY_COMPLETE skip production launch"
else
  if ! bash "${RUNTIME}/benchmark_parallel_6.sh" > "${PARALLEL_LOG}" 2>&1; then
    log "GATE_FAILED six-job parallel benchmark"
    exit 1
  fi

  parallel_wall=$(sed -n \
    's/.*PARALLEL_BENCHMARK_COMPLETE.*wall_seconds=\([0-9][0-9]*\).*/\1/p' \
    "${PARALLEL_LOG}" | tail -1)
  if [[ -z "${parallel_wall}" || "${parallel_wall}" -le 0 ]]; then
    log "GATE_FAILED cannot parse parallel benchmark wall time"
    exit 1
  fi
  # Single-job production benchmark: 5149.276 s / 6 model months.
  speedup=$(awk -v baseline="858.212667" -v wall="${parallel_wall}" \
    'BEGIN {printf "%.3f", 6.0 * baseline / wall}')
  if awk -v value="${speedup}" 'BEGIN {exit !(value >= 4.5)}'; then
    selected_parallel=6
  elif awk -v value="${speedup}" 'BEGIN {exit !(value >= 3.0)}'; then
    selected_parallel=4
  else
    selected_parallel=2
  fi
  log "GATE_PARALLEL_BENCHMARK wall_seconds=${parallel_wall} speedup=${speedup} selected_parallel=${selected_parallel}"

  if ! MAX_PARALLEL="${selected_parallel}" \
      bash "${RUNTIME}/run_p0_screening.sh" > "${P0_LOG}" 2>&1; then
    log "GATE_FAILED P0 production matrix"
    exit 1
  fi
  log "GATE_P0_RUN_COMPLETE"
fi

if ! "${ANALYSIS_PY}" "${RUNTIME}/verify_and_summarize_p0.py" \
    --data "${RUNTIME}/data" \
    --output "${RESULT_DIR}" \
    --members 10 \
    --months 6 \
    >> "${GATE_LOG}" 2>&1; then
  log "GATE_FAILED P0 full verification"
  exit 1
fi
log "GATE_P0_VERIFIED"

mkdir -p /root/autodl-tmp/p0_mplconfig
if ! MPLCONFIGDIR=/root/autodl-tmp/p0_mplconfig \
    "${ANALYSIS_PY}" "${RUNTIME}/plot_p0_screening_results.py" \
      --input "${RESULT_DIR}" \
      --output "${FIGURE_DIR}" \
      >> "${GATE_LOG}" 2>&1; then
  log "GATE_FAILED P0 figure generation"
  exit 1
fi
log "GATE_P0_FIGURES_COMPLETE"

p0_wall=$(sed -n \
  's/.*P0_SCREENING_COMPLETE.*wall_seconds=\([0-9][0-9]*\).*/\1/p' \
  "${P0_LOG}" | tail -1)
if [[ -n "${p0_wall}" && "${p0_wall}" -gt 0 ]]; then
  p0_cost=$(awk -v seconds="${p0_wall}" -v price="${PRICE_PER_HOUR}" \
    'BEGIN {printf "%.2f", seconds / 3600.0 * price}')
else
  p0_wall="unknown"
  p0_cost="unknown"
fi

{
  echo "P0_PIPELINE_COMPLETE $(date -Is)"
  echo "p0_wall_seconds=${p0_wall}"
  echo "p0_wall_cost_cny=${p0_cost}"
  echo "price_per_hour_cny=${PRICE_PER_HOUR}"
  echo "result_dir=${RESULT_DIR}"
} > "${RESULT_DIR}/pipeline_summary.txt"
log "P0_PIPELINE_COMPLETE p0_wall_seconds=${p0_wall} p0_cost_cny=${p0_cost}"
