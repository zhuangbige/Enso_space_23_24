#!/usr/bin/env bash
set -euo pipefail

ISCA_RUNTIME_DIR="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
ISCA_ENV_PREFIX="${ISCA_ENV_PREFIX:-/root/autodl-tmp/isca_env}"
MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-/root/autodl-tmp/mamba_root}"
MICROMAMBA="${MICROMAMBA:-/root/autodl-tmp/bin/micromamba}"
LOG_DIR="${ISCA_RUNTIME_DIR}/logs"
mkdir -p "${LOG_DIR}" /root/autodl-tmp/bin

if [[ ! -x "${MICROMAMBA}" ]]; then
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xj -C /root/autodl-tmp bin/micromamba
fi

if [[ ! -x "${ISCA_ENV_PREFIX}/bin/python" ]]; then
  MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${MICROMAMBA}" create -y \
    -p "${ISCA_ENV_PREFIX}" \
    -f "${ISCA_RUNTIME_DIR}/Isca/ci/environment-py3.12_frozen.yml"
fi

"${ISCA_ENV_PREFIX}/bin/python" -m pip install -e \
  "${ISCA_RUNTIME_DIR}/Isca/src/extra/python"

# shellcheck disable=SC1091
source "${ISCA_RUNTIME_DIR}/activate_isca_linux.sh"

{
  echo "HOST=$(hostname)"
  echo "NPROC=$(nproc)"
  python --version
  mpifort --version | head -n 1
  nf-config --version
} | tee "${LOG_DIR}/environment_summary.txt"

python "${ISCA_RUNTIME_DIR}/checks/compile_full_isca.py" \
  2>&1 | tee "${LOG_DIR}/compile_full_isca.log"

echo "BOOTSTRAP_AUTODL_OK" | tee "${LOG_DIR}/bootstrap_status.txt"
