#!/usr/bin/env bash
set -u

RUNTIME="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
PREFIX="${ISCA_ENV_PREFIX:-/root/autodl-tmp/isca_env}"
MEMBERS="${MEMBERS:-10}"
CORES_PER_JOB="${CORES_PER_JOB:-4}"
MAX_PARALLEL="${MAX_PARALLEL:-6}"
MPIRUN_OPTS="${MPIRUN_OPTS:---bind-to none}"
SOURCE_POOL="${RUNTIME}/data/isca_control_ensemble_pool_t42/restarts"
DEST_POOL="${RUNTIME}/data/isca_control_march_pool_t42/restarts"
LOG_DIR="${RUNTIME}/logs/march_aligned_pool"
FAIL_FILE="${LOG_DIR}/failures.txt"

export PATH="${PREFIX}/bin:${PATH}"
export GFDL_BASE="${RUNTIME}/Isca"
export GFDL_ENV=ubuntu_conda
export GFDL_WORK="${RUNTIME}/work"
export GFDL_DATA="${RUNTIME}/data"
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export OMPI_MCA_btl_vader_single_copy_mechanism=none

mkdir -p "${DEST_POOL}" "${LOG_DIR}"
: > "${FAIL_FILE}"
START_EPOCH=$(date +%s)
echo "MARCH_ALIGNED_POOL_START $(date -Is) members=${MEMBERS} cores=${CORES_PER_JOB} max_parallel=${MAX_PARALLEL}"

run_one() {
  local member="$1"
  local source
  local destination
  local log_file
  local start_seconds
  local end_seconds
  local wall_seconds
  source=$(printf "%s/res%04d.tar.gz" "${SOURCE_POOL}" "${member}")
  destination=$(printf "%s/res%04d.tar.gz" "${DEST_POOL}" "${member}")
  log_file=$(printf "%s/member_%02d.log" "${LOG_DIR}" "${member}")

  if [[ -s "${destination}" ]] && \
      tar -xOzf "${destination}" ./atmos_model.res 2>/dev/null | head -n 1 | \
      awk '{exit !($1==2023 && $2==3 && $3==1 && $4==0 && $5==0 && $6==0)}'; then
    echo "SKIP $(date -Is) member=${member} destination=${destination}" >> "${log_file}"
    return 0
  fi
  if [[ ! -s "${source}" ]]; then
    echo "missing_source member=${member} file=${source}" >> "${FAIL_FILE}"
    return 1
  fi

  echo "START $(date -Is) member=${member}" > "${log_file}"
  start_seconds=$(date +%s.%N)
  if python "${RUNTIME}/run_control_member_to_march.py" \
      --member "${member}" \
      --source-restart "${source}" \
      --destination "${destination}" \
      --months 3 \
      --cores "${CORES_PER_JOB}" \
      --mpirun-opts "${MPIRUN_OPTS}" \
      --overwrite >> "${log_file}" 2>&1; then
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds}" >> "${log_file}"
    echo "DONE $(date -Is) member=${member}" >> "${log_file}"
  else
    local status=$?
    end_seconds=$(date +%s.%N)
    wall_seconds=$(awk -v start="${start_seconds}" -v end="${end_seconds}" \
      'BEGIN {printf "%.3f", end - start}')
    echo "WALL_SECONDS=${wall_seconds} EXIT_STATUS=${status}" >> "${log_file}"
    echo "FAILED member=${member} status=${status}" >> "${FAIL_FILE}"
    return "${status}"
  fi
}

for member in $(seq 1 "${MEMBERS}"); do
  while (( $(jobs -pr | wc -l) >= MAX_PARALLEL )); do
    wait -n || true
  done
  run_one "${member}" &
done
wait

if [[ -s "${FAIL_FILE}" ]]; then
  cat "${FAIL_FILE}"
  exit 1
fi
END_EPOCH=$(date +%s)
grep -h 'WALL_SECONDS=' "${LOG_DIR}"/member_*.log
echo "MARCH_ALIGNED_POOL_COMPLETE members=${MEMBERS} wall_seconds=$((END_EPOCH - START_EPOCH))"
