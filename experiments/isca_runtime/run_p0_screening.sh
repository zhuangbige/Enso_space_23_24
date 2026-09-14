#!/usr/bin/env bash
set -u

RUNTIME="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
PREFIX="${ISCA_ENV_PREFIX:-/root/autodl-tmp/isca_env}"
ANALYSIS_PY="${ISCA_ANALYSIS_PY:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
MEMBERS="${MEMBERS:-10}"
MONTHS="${MONTHS:-6}"
CORES_PER_JOB="${CORES_PER_JOB:-4}"
MAX_PARALLEL="${MAX_PARALLEL:-6}"
MPIRUN_OPTS="${MPIRUN_OPTS:---bind-to none}"

export PATH="${PREFIX}/bin:${PATH}"
export GFDL_BASE="${RUNTIME}/Isca"
export GFDL_ENV=ubuntu_conda
export GFDL_WORK="${RUNTIME}/work"
export GFDL_DATA="${RUNTIME}/data"
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export OMPI_MCA_btl_vader_single_copy_mechanism=none

LOG_DIR="${RUNTIME}/logs/p0_screening"
FAIL_FILE="${LOG_DIR}/failures.txt"
mkdir -p "${LOG_DIR}"
: > "${FAIL_FILE}"

if ! "${ANALYSIS_PY}" -c \
    "import json; d=json.load(open('${RUNTIME}/results/p0_screening/march_aligned_pool_validation.json')); assert d['complete'] and d['valid_state_hashes']==10 and d['unique_state_hashes']==10"; then
  echo "March-aligned restart pool has not passed the 10-member audit" >> "${FAIL_FILE}"
  cat "${FAIL_FILE}"
  exit 1
fi

CASES=(ia0_fep0 ia0_fep1 ia1_fep0 ia1_fep1)
START_EPOCH=$(date +%s)
echo "P0_SCREENING_START $(date -Is) members=${MEMBERS} months=${MONTHS} cores=${CORES_PER_JOB} max_parallel=${MAX_PARALLEL} mpirun_opts=${MPIRUN_OPTS}"

run_one() {
  local case_name="$1"
  local member="$2"
  local restart
  local log_file
  local final_output
  restart=$(printf "%s/data/isca_control_march_pool_t42/restarts/res%04d.tar.gz" \
    "${RUNTIME}" "${member}")
  log_file=$(printf "%s/%s_m%02d.log" "${LOG_DIR}" "${case_name}" "${member}")
  final_output=$(printf "%s/data/isca_2023_%s_m%02d_t42/run%04d/atmos_monthly.nc" \
    "${RUNTIME}" "${case_name}" "${member}" "${MONTHS}")

  if [[ -s "${final_output}" ]]; then
    echo "SKIP $(date -Is) ${case_name} member=${member} final_output=${final_output}" >> "${log_file}"
    return 0
  fi

  if [[ ! -f "${restart}" ]]; then
    echo "missing_restart ${case_name} ${member} ${restart}" >> "${FAIL_FILE}"
    return 1
  fi
  if ! tar -xOzf "${restart}" ./atmos_model.res 2>/dev/null | head -n 1 | \
      awk '{exit !($1==2023 && $2==3 && $3==1 && $4==0 && $5==0 && $6==0)}'; then
    echo "invalid_restart_date ${case_name} ${member} ${restart}" >> "${FAIL_FILE}"
    return 1
  fi

  echo "START $(date -Is) ${case_name} member=${member}" > "${log_file}"
  local start_seconds
  local end_seconds
  local wall_seconds
  start_seconds=$(date +%s.%N)
  if python "${RUNTIME}/run_2023_factorial.py" \
      --case "${case_name}" \
      --member "${member}" \
      --months "${MONTHS}" \
      --cores "${CORES_PER_JOB}" \
      --mpirun-opts "${MPIRUN_OPTS}" \
      --restart "${restart}" \
      --overwrite >> "${log_file}" 2>&1; then
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds}" >> "${log_file}"
    echo "DONE $(date -Is) ${case_name} member=${member}" >> "${log_file}"
  else
    status=$?
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds} EXIT_STATUS=${status}" >> "${log_file}"
    echo "FAILED ${case_name} ${member} status=${status}" >> "${FAIL_FILE}"
    return "${status}"
  fi
}

for member in $(seq 1 "${MEMBERS}"); do
  for case_name in "${CASES[@]}"; do
    while (( $(jobs -pr | wc -l) >= MAX_PARALLEL )); do
      wait -n || true
    done
    run_one "${case_name}" "${member}" &
  done
done
wait

if [[ -s "${FAIL_FILE}" ]]; then
  cat "${FAIL_FILE}"
  exit 1
fi

END_EPOCH=$(date +%s)
echo "P0_SCREENING_COMPLETE members=${MEMBERS} cases=${#CASES[@]} wall_seconds=$((END_EPOCH - START_EPOCH))"
