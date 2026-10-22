#!/usr/bin/env bash
set -euo pipefail

unzip -o wheels.zip
mkdir -p eapburst-libs

PIP_WHEEL=$(find ./wheels -maxdepth 1 -name 'pip-*.whl' -print -quit)
if [[ -z "$PIP_WHEEL" ]]; then
    echo "pip wheel not found in ./wheels" >&2
    exit 1
fi

PYTHONPATH="$PIP_WHEEL" python3 -m pip install \
    --no-index \
    --find-links ./wheels \
    --target ./eapburst-libs \
    twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL click

PYTHONPATH=./eapburst-libs python3 -c \
    'import twisted, txdbus, wpa_supplicant, service_identity; print("Dependencies installed")'
EOF
