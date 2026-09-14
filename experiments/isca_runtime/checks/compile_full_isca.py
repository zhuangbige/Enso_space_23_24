"""Compile Isca with moist physics and RRTM radiation."""

from isca import GFDL_BASE, IscaCodeBase


codebase = IscaCodeBase.from_directory(GFDL_BASE)
codebase.compile()
print(f"ISCA_FULL_COMPILE_OK {codebase.executable_fullpath}")
