# EAPBurst

Perform controlled, online WPA-Enterprise credential validation against a target SSID using PEAP/MSCHAPv2. EAPBurst distributes username attempts across one or more wireless interfaces and records credentials accepted by the test network.

Use this project only during an authorized wireless assessment or in an isolated lab. It is not a passive capture tool and it does not recover credentials from a packet capture.

---

## Overview

`eapburst.py` automates the following assessment workflow:

- Reads usernames from a file.
- Tests one supplied password against each username, or combines username and password files.
- Uses one worker per wireless interface.
- Controls `wpa_supplicant` through its D-Bus interface.
- Waits for association and authentication results before recording an attempt.
- Supports resuming from a username-file line.
- Optionally stops after the first valid credential and writes results to CSV.

The tool is intended for validating whether scoped accounts can authenticate to a test SSID. Use it only with written authorization, a defined scope, and a rate that will not disrupt the wireless environment.

---

## Features

- Concurrent attempts across multiple wireless interfaces.
- PEAP/MSCHAPv2 authentication through the host's `wpa_supplicant` service.
- Single-password or password-list mode.
- Resume support using a starting username-file line.
- Configurable association timeout and polling interval.
- Optional delay between attempts for rate control.
- CSV output for accepted credentials.
- Stop-on-success mode.
- Clear dependency and interface error reporting.
- Works with Python 3.11 and Python 3.13 when compatible dependency packages are installed for the selected interpreter.

---

## Functions and Components

### Argument parser

Validates the SSID, interface list, username file, password source, timing values, and output path before workers are started.

### Dependency loader

Checks that the required Python modules are importable and reports missing packages instead of failing with an opaque traceback. Runtime dependencies are:

- `twisted`
- `wpa_supplicant`
- `txdbus`
- `service_identity`
- `cryptography`
- `pyOpenSSL`

Exact package versions must match the Python version and architecture of the assessment host.

### Wireless worker

Each worker owns one interface and performs one association attempt at a time. Supplying two interfaces creates two concurrent workers; supplying one interface creates one worker.

### Result writer

Accepted credentials can be written to the CSV file supplied with `-w`. Protect the output because it may contain plaintext credentials.

---

## Usage

### Basic command

```bash
python3 ./eapburst.py -i wlan0 -e Test-Network -P UserPassword1 -u usernames.txt
```

### Two-interface run

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -P UserPassword1 -u usernames.txt
```

### Password-list run

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -p passwords.txt -u usernames.txt
```

`-P` and `-p` are mutually exclusive. Use `-P` when every username is tested with one password; use `-p` when every username must be tested against a password list.

### Resume from a username line

```bash
python3 ./eapburst.py \
    -i wlan0 \
    -e Test-Network \
    -P UserPassword1 \
    -u usernames.txt \
    -s 250
```

### Stop after the first accepted credential

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -P UserPassword1 -u usernames.txt -1
```

### Save accepted credentials

```bash
python3 ./eapburst.py \
    -i wlan0,wlan1 \
    -e Test-Network \
    -P UserPassword1 \
    -u usernames.txt \
    -w accepted.csv
```

### Rate-limit attempts and tune timeouts

```bash
python3 ./eapburst.py \
    -i wlan0,wlan1 \
    -e Test-Network \
    -p passwords.txt \
    -u usernames.txt \
    -t 3 \
    --max-wait 30 \
    --test-interval 0.5
```

### Show all options

```bash
python3 ./eapburst.py --help
```

Expected option summary:

```text
-i interface[,interface...]  Wireless interface or comma-separated interfaces
-e SSID                       Target WPA-Enterprise SSID
-u USERFILE                   Username wordlist
-P PASSWORD                   One password for every username
-p PASSFILE                   Password wordlist
-s line                       Username-file line at which to resume
-w OUTFILE                    CSV output for accepted credentials
-1                            Stop after the first success
-t seconds                    Delay between attempts per worker
--max-wait seconds            Maximum wait for association/authentication
--test-interval seconds       Polling interval while waiting for state
```

---

## Requirements

- Linux host with one or more supported wireless interfaces.
- Python 3.11 or Python 3.13.
- `wpa_supplicant` installed as a system binary and able to control the interfaces.
- D-Bus available and the `wpa_supplicant` control interface enabled.
- Root privileges or equivalent permission to control wireless interfaces and D-Bus.
- A username file, plus either one password or a password file.
- Authorization to test the target SSID and identities.

Check the host before running:

```bash
python3 --version
command -v wpa_supplicant
systemctl status dbus --no-pager
systemctl status wpa_supplicant --no-pager
ip link show
iw dev
```

Check Python imports:

```bash
python3 -c 'import twisted, txdbus, wpa_supplicant, service_identity, cryptography, OpenSSL; print("dependencies OK")'
```

---

## Installation

### Online installation

Install dependencies for the interpreter that will run the script:

```bash
python3 -m pip install twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

On Debian or Ubuntu systems using PEP 668, use a virtual environment where available:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

If a controlled lab explicitly requires system-wide installation, the package manager may require `--break-system-packages`. Use that only on a disposable assessment host.

### Offline installation

On an internet-connected staging system, download packages for the target Python version and architecture:

```bash
python3 -m pip download \
    --dest wheels \
    twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

Transfer the complete `wheels` directory to the assessment host, then install without contacting an index:

```bash
python3 -m pip install \
    --no-index \
    --find-links ./wheels \
    twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

For Python 3.11, the bundle must contain cp311-compatible wheels where a compiled package is required. For Python 3.13, use cp313-compatible wheels. Do not mix a cp313 `cffi` or `zope-interface` wheel into a Python 3.11 bundle.

Verify the result:

```bash
python3 -c 'import twisted, txdbus, wpa_supplicant, service_identity, cryptography, OpenSSL; print("offline dependencies OK")'
```

### Script installation

```bash
chmod +x ./eapburst.py
python3 ./eapburst.py --help
```

---

## Troubleshooting

### `Missing runtime dependency: twisted`

Install into the same Python environment used to run the script:

```bash
python3 -m pip install twisted
python3 -c 'import twisted; print(twisted.__version__)'
```

### `Missing runtime dependency: wpa_supplicant`

Install the package and its local dependencies:

```bash
python3 -m pip install wpa_supplicant txdbus
python3 -c 'import wpa_supplicant, txdbus; print("wpa_supplicant bindings OK")'
```

### `No module named service_identity`

```bash
python3 -m pip install service_identity
```

When offline, include `service_identity`, `cryptography`, `cffi`, and `pycparser` in the local package directory.

### `AttributeError: module 'lib' has no attribute 'GEN_EMAIL'`

This normally indicates an incompatible `pyOpenSSL` and `cryptography` combination. Reinstall both as a compatible pair:

```bash
python3 -m pip install --upgrade --force-reinstall cryptography pyOpenSSL
python3 -c 'from OpenSSL import SSL; print("OpenSSL bindings OK")'
```

For an offline host, download matching versions together. Do not combine a newer `cryptography` package with an old system `pyOpenSSL`.

### `externally-managed-environment`

Use a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links ./wheels twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

### Interface or D-Bus initialization fails

Confirm that the interface exists, is not already controlled by NetworkManager, and is not used by another wireless process:

```bash
ip link show wlan0
iw dev wlan0 info
nmcli device status
ps aux | grep -E '[w]pa_supplicant|[N]etworkManager'
```

Do not run multiple wireless tools against the same interface simultaneously. Restore connection-manager state after testing.

### Authentication attempts time out

Keep the interface on the target channel, verify the SSID and security mode, and increase the wait period:

```bash
python3 ./eapburst.py \
    -i wlan0 \
    -e Test-Network \
    -P UserPassword1 \
    -u usernames.txt \
    --max-wait 45 \
    --test-interval 1
```

### Results are not written

Confirm that the output directory is writable:

```bash
touch ./accepted.csv
ls -l ./accepted.csv
```

---

## Operational Notes

- The interface count controls concurrency; four interfaces create four workers.
- A failed authentication is not proof that an account is invalid because radio conditions, channel changes, certificates, server policy, lockout controls, and supplicant state can affect results.
- Avoid aggressive retry rates. Coordinate with the wireless owner and monitor account-lockout and service-impact thresholds.
- Treat usernames, passwords, CSV output, and debug logs as sensitive assessment data.
- Restore NetworkManager, `wpa_supplicant`, and interface state after testing.

---

## Disclaimer

This project is intended solely for educational use, defensive validation, and authorized penetration testing. Run it only against wireless networks and identities for which you have explicit written permission and a defined scope. Online authentication testing can trigger account lockouts, alerts, or service disruption. Obtain approval before testing production networks, use the lowest practical rate, protect all captured credentials, and securely delete assessment output when it is no longer required.

The authors assume no liability for unauthorized access, service disruption, data loss, credential exposure, or any other misuse of this project.

---

## Author

- :skull: **B5null**

