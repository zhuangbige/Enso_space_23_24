#!/usr/bin/env bash
set -u

RUNTIME="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
PREFIX="${ISCA_ENV_PREFIX:-/root/autodl-tmp/isca_env}"
ANALYSIS_PY="${ISCA_ANALYSIS_PY:-/root/autodl-tmp/isca_env_broken_20260801_1410/bin/python}"
CORES_PER_JOB="${CORES_PER_JOB:-4}"
PARALLEL_JOBS="${PARALLEL_JOBS:-6}"
MPIRUN_OPTS="${MPIRUN_OPTS:---bind-to none}"

export PATH="${PREFIX}/bin:${PATH}"
export GFDL_BASE="${RUNTIME}/Isca"
export GFDL_ENV=ubuntu_conda
export GFDL_WORK="${RUNTIME}/work"
export GFDL_DATA="${RUNTIME}/data"
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export OMPI_MCA_btl_vader_single_copy_mechanism=none

LOG_DIR="${RUNTIME}/logs/parallel_${PARALLEL_JOBS}_benchmark"
FAIL_FILE="${LOG_DIR}/failures.txt"
mkdir -p "${LOG_DIR}"
: > "${FAIL_FILE}"
START_EPOCH=$(date +%s)
echo "PARALLEL_BENCHMARK_START $(date -Is) jobs=${PARALLEL_JOBS} cores=${CORES_PER_JOB} mpirun_opts=${MPIRUN_OPTS}"

run_one() {
  local index="$1"
  local member=$((89 + index))
  local restart
  local log_file
  restart=$(printf "%s/data/isca_control_march_pool_t42/restarts/res%04d.tar.gz" \
    "${RUNTIME}" "${index}")
  log_file=$(printf "%s/job_%02d_member_%02d.log" "${LOG_DIR}" "${index}" "${member}")
  if [[ ! -s "${restart}" ]]; then
    echo "missing_restart index=${index} file=${restart}" >> "${FAIL_FILE}"
    return 1
  fi
  echo "START $(date -Is) index=${index} member=${member}" > "${log_file}"
  local start_seconds
  local end_seconds
  local wall_seconds
  start_seconds=$(date +%s.%N)
  if python "${RUNTIME}/run_2023_factorial.py" \
        --case ia0_fep0 \
        --member "${member}" \
        --months 1 \
        --cores "${CORES_PER_JOB}" \
        --mpirun-opts "${MPIRUN_OPTS}" \
        --restart "${restart}" \
        --overwrite >> "${log_file}" 2>&1; then
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds}" >> "${log_file}"
    echo "DONE $(date -Is) index=${index} member=${member}" >> "${log_file}"
  else
    local status=$?
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds} EXIT_STATUS=${status}" >> "${log_file}"
    echo "FAILED index=${index} member=${member} status=${status}" >> "${FAIL_FILE}"
    return "${status}"
  fi
}

for index in $(seq 1 "${PARALLEL_JOBS}"); do
  run_one "${index}" &
done
wait

END_EPOCH=$(date +%s)
if [[ -s "${FAIL_FILE}" ]]; then
  cat "${FAIL_FILE}"
  exit 1
fi

for index in $(seq 1 "${PARALLEL_JOBS}"); do
  member=$((89 + index))
  output=$(printf "%s/data/isca_2023_ia0_fep0_m%02d_t42/run0001/atmos_monthly.nc" \
    "${RUNTIME}" "${member}")
  if [[ ! -s "${output}" ]]; then
    echo "missing_output index=${index} member=${member} file=${output}" >> "${FAIL_FILE}"
  fi
done
if [[ -s "${FAIL_FILE}" ]]; then
  cat "${FAIL_FILE}"
  exit 1
fi

if ! "${ANALYSIS_PY}" "${RUNTIME}/validate_parallel_benchmark_outputs.py" \
    --data "${RUNTIME}/data" \
    --jobs "${PARALLEL_JOBS}" \
    --output "${RUNTIME}/results/p0_screening/parallel_benchmark_validation.json"; then
  echo "parallel_output_scientific_validation_failed" >> "${FAIL_FILE}"
  exit 1
fi

grep -h 'WALL_SECONDS=' "${LOG_DIR}"/job_*.log
echo "PARALLEL_BENCHMARK_COMPLETE jobs=${PARALLEL_JOBS} wall_seconds=$((END_EPOCH - START_EPOCH))"
