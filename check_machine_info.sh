#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY' > target-info.txt
import platform
import subprocess
import sys

glibc = subprocess.check_output(
    ["getconf", "GNU_LIBC_VERSION"], text=True
).strip().split()[-1]

print(f"PYTHON_VERSION={sys.version_info.major}.{sys.version_info.minor}")
print(f"ARCH={platform.machine()}")
print(f"GLIBC_VERSION={glibc}")
PY

cat target-info.txt
