#!/usr/bin/env bash
# Source this file before running the local Isca experiment scripts.

ISCA_RUNTIME_DIR="/Users/daiyue/Documents/Maryland/experiments/isca_runtime"
export PATH="${ISCA_RUNTIME_DIR}/env_py312/bin:${PATH}"
export GFDL_BASE="${ISCA_RUNTIME_DIR}/Isca"
export GFDL_ENV="macos_arm64_conda"
export GFDL_WORK="${ISCA_RUNTIME_DIR}/work"
export GFDL_DATA="${ISCA_RUNTIME_DIR}/data"

echo "Isca environment active: ${GFDL_BASE}"
