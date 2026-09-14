#!/usr/bin/env bash
# Activate the Linux/x86_64 Isca runtime used on the AutoDL instance.

ISCA_RUNTIME_DIR="${ISCA_RUNTIME_DIR:-/root/autodl-tmp/isca_runtime}"
ISCA_ENV_PREFIX="${ISCA_ENV_PREFIX:-/root/autodl-tmp/isca_env}"

if [[ -x "${ISCA_ENV_PREFIX}/bin/python" ]]; then
  export PATH="${ISCA_ENV_PREFIX}/bin:${PATH}"
elif [[ -f /root/miniconda3/etc/profile.d/conda.sh ]]; then
  # shellcheck disable=SC1091
  source /root/miniconda3/etc/profile.d/conda.sh
  conda activate isca_env
else
  echo "Isca environment not found: ${ISCA_ENV_PREFIX}" >&2
  return 1 2>/dev/null || exit 1
fi

export GFDL_BASE="${ISCA_RUNTIME_DIR}/Isca"
export GFDL_ENV="ubuntu_conda"
export GFDL_WORK="${ISCA_RUNTIME_DIR}/work"
export GFDL_DATA="${ISCA_RUNTIME_DIR}/data"

# AutoDL containers run as root; OpenMPI otherwise refuses to launch.
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export OMPI_MCA_btl_vader_single_copy_mechanism=none

mkdir -p "${GFDL_WORK}" "${GFDL_DATA}"
echo "Isca Linux environment active: ${GFDL_BASE}"
