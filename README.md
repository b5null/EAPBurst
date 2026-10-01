# EAPBurst – WPA Enterprise Bruteforcing

`eapburst.py` performs authorized online PEAP/MSCHAPv2 authentication testing against a WPA-Enterprise network. It tests usernames using one password or a password list, with one worker per wireless interface.

Attempts are generated incrementally through a bounded queue, avoiding loading every username/password combination into memory.

---

## Features

- Username list input.
- One shared password or a password list.
- Multiple wireless interfaces for controlled concurrency.
- Streaming attempt generation with bounded memory use.
- Start from a selected username index.
- Optional CSV output.
- Configurable delay and authentication wait time.

---

## Requirements

- Linux and one or more supported wireless interfaces.
- Python 3 with compatible dependency packages.
- System `wpa_supplicant` installed and accessible through D-Bus.
- Python dependencies: `twisted`, `wpa_supplicant`, `txdbus`, `service_identity`, `cryptography`, and `pyOpenSSL`.
- Authorization to test the target network and accounts.

Install online:

```bash
python3 -m pip install twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL
```

For an offline host, prepare the dependencies on a connected system using the target’s Python minor version and architecture, with a compatible Linux environment:

```bash
mkdir -p wheels
python3 -m pip wheel --wheel-dir ./wheels twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL
```

This downloads dependencies and builds source packages into wheels before transfer.

Transfer the `wheels` directory to the target, then install:

```bash
python3 -m pip install --no-index --find-links ./wheels twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL
```

Check the interpreter and architecture on both systems:

```bash
python3 --version
uname -m
```

Native wheels must match the target interpreter and platform. A downloader using a different Python minor version can select incompatible packages.

If pip reports an externally managed environment, install inside a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
```

Then rerun the installation command.

---

## Usage

```text
usage: eapburst.py -i INTERFACES -e SSID -u USERFILE
                   (-P PASSWORD | -p PASSFILE) [-s INDEX] [-w OUTFILE]
                   [-1] [-t SECONDS] [--max-wait SECONDS]
                   [--test-interval SECONDS]

-i INTERFACES       Interface name or comma-separated interface names
-e SSID             Target WPA-Enterprise network
-u USERFILE         Usernames, one per line
-P PASSWORD         One password to test for each username
-p PASSFILE         Passwords, one per line
-s INDEX            Start at this zero-based, nonempty username index
-w OUTFILE          Write accepted credentials to CSV
-1                  Stop after the first accepted credential
-t SECONDS          Delay between attempts per worker
--max-wait SECONDS  Maximum wait for each authentication attempt
--test-interval SEC Polling interval while waiting for authentication state
```

Use exactly one of `-P` or `-p`. Each interface runs one worker.

By default, all combinations are tested. Add `-1` to stop after the first successful authentication. Attempts already running on other interfaces may finish.

With a password list, `-s` applies the selected username index to every password. It does not restore a saved password-list position.

---

## Examples

Single interface and one password:

```bash
python3 eapburst.py -i wlan0 -e Test-Network -P 'ExamplePassword' -u users.txt
```

Two interfaces and one password:

```bash
python3 eapburst.py -i wlan0,wlan1 -e Test-Network -P 'ExamplePassword' -u users.txt
```

Username and password lists, with a delay and CSV output:

```bash
python3 eapburst.py \
    -i wlan0,wlan1 \
    -e Test-Network \
    -u users.txt \
    -p passwords.txt \
    -t 3 \
    -w results.csv
```

Stop after the first successful authentication:

```bash
python3 eapburst.py -i wlan0 -e Test-Network -u users.txt -p passwords.txt -1
```

Start from username index 250:

```bash
python3 eapburst.py -i wlan0 -e Test-Network -P 'ExamplePassword' -u users.txt -s 250
```

Show help:

```bash
python3 eapburst.py --help
```

---

## Notes and OPSEC

- Authentication attempts may trigger account lockouts and security alerts.
- Keep the attempt rate and interface count within the approved scope.
- Coordinate testing with the network owner or SOC.
- Treat username lists, terminal output, and CSV files as sensitive data.

---

## Disclaimer

For educational and authorized security testing only. Use this tool only against networks and accounts for which you have explicit permission. The authors assume no liability for unauthorized use, account lockouts, service disruption, or other misuse.

---

## Author

- :skull: **B5null**
