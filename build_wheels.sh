#!/usr/bin/env bash
set -euo pipefail

INFO="${1:-target-info.txt}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "$INFO" ]]; then
    exit 1
fi

source "$INFO"

PYTHON_ABI="cp${PYTHON_VERSION/./}"
GLIBC_MAJOR="${GLIBC_VERSION%%.*}"
GLIBC_MINOR="${GLIBC_VERSION#*.}"
PLATFORM="manylinux_${GLIBC_MAJOR}_${GLIBC_MINOR}_${ARCH}"
PLATFORM_2014="manylinux2014_${ARCH}"

EXTRA_DEPS=()
if [[ "$PYTHON_VERSION" == 3.* ]] && (( ${PYTHON_VERSION#*.} < 11 )); then
    EXTRA_DEPS+=(tomli)
fi

rm -rf wheels wheels.zip
mkdir -p wheels

"$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir ./wheels \
    "wpa_supplicant==0.2"

"$PYTHON_BIN" -m pip download --dest wheels --no-deps \
    --only-binary=:all: --python-version "$PYTHON_VERSION" pip

"$PYTHON_BIN" -m pip download \
    --dest wheels \
    --only-binary=:all: \
    --implementation cp \
    --python-version "$PYTHON_VERSION" \
    --abi "$PYTHON_ABI" \
    --abi abi3 \
    --abi none \
    --platform "$PLATFORM" \
    --platform "$PLATFORM_2014" \
    twisted txdbus service_identity cryptography pyOpenSSL click \
    "${EXTRA_DEPS[@]}"

"$PYTHON_BIN" - <<'PY'
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

with ZipFile("wheels.zip", "w", ZIP_DEFLATED) as archive:
    for path in Path("wheels").rglob("*"):
        if path.is_file():
            archive.write(path, path.as_posix())
PY
EOF
