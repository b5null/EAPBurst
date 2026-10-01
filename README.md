# EAPBurst – WPA Enterprise Bruteforcing

`eapburst.py` performs authorized online PEAP/MSCHAPv2 authentication testing against a WPA-Enterprise network. It tests usernames using one password or a password list, with one worker per wireless interface.

---

## Features

- Username list input.
- One shared password or a password list.
- Multiple wireless interfaces for controlled concurrency.
- Resume from a selected username-file line.
- Optional CSV output and stop-after-first-success mode.
- Configurable delay and authentication wait time.

---

## Requirements

- Linux and one or more supported wireless interfaces.
- Python 3.11 or 3.13, with packages compatible with that interpreter.
- `wpa_supplicant` installed and accessible through D-Bus.
- Python dependencies: `twisted`, `wpa_supplicant`, `txdbus`, `service_identity`, `cryptography`, and `pyOpenSSL`.
- Authorization to test the target network and accounts.

Install online:

```bash
python3 -m pip install twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

For an offline host, prepare compatible packages on a connected system by downloading them:

```bash
mkdir -p wheels
python3 -m pip download -d wheels twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

Transfer them in a directory named `wheels`, then install:

```bash
python3 -m pip install --no-index --find-links ./wheels twisted wpa_supplicant service_identity cryptography pyOpenSSL
```

Use wheels matching the target Python version and architecture.

---

## Usage

```text
usage: eapburst.py -i INTERFACES -e SSID -u USERFILE
                   [-P PASSWORD | -p PASSFILE] [-s LINE] [-w OUTFILE]
                   [-1] [-t SECONDS] [--max-wait SECONDS]
                   [--test-interval SECONDS]

-i INTERFACES       Interface name or comma-separated interface names
-e SSID             Target WPA-Enterprise network
-u USERFILE         Usernames, one per line
-P PASSWORD         One password to test for each username
-p PASSFILE         Passwords, one per line
-s LINE             Resume from this username-file line
-w OUTFILE          Write accepted credentials to CSV
-1                  Stop after the first accepted credential
-t SECONDS          Delay between attempts per worker
--max-wait SECONDS  Maximum wait for each authentication attempt
--test-interval SEC Polling interval while waiting for authentication state
```

Use either `-P` or `-p`, not both. Each interface runs one worker.

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

Resume from line 250:

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
- Treat username lists and CSV output as sensitive data.

---

## Disclaimer

For educational and authorized security testing only. Use this tool only against networks and accounts for which you have explicit permission. The authors assume no liability for unauthorized use, account lockouts, service disruption, or other misuse.

---

## Author

- :skull: **B5null**

