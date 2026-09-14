"""Compile Isca's smallest dry dynamical-core configuration."""

from isca import DryCodeBase, GFDL_BASE


codebase = DryCodeBase.from_directory(GFDL_BASE)
codebase.compile()
print(f"ISCA_COMPILE_OK {codebase.executable_fullpath}")
