# EAPBurst – WPA Enterprise Authentication Testing

EAPBurst performs authorized online PEAP/MSCHAPv2 authentication testing against WPA-Enterprise networks. It tests a username list with one shared password or a password list, using one worker per wireless interface.

Attempts are generated incrementally through a bounded queue, so the complete username/password matrix is not loaded into memory.

## Features

- PEAP/MSCHAPv2 authentication testing.
- One shared password or a password list.
- Multiple wireless interfaces for controlled concurrency.
- One worker per interface.
- Streaming attempt generation with bounded memory use.
- Resume from a selected username index.
- Optional CSV output for successful credentials.
- Configurable authentication timeout, polling interval, and inter-attempt delay.
- Optional stop after the first successful authentication.

## Turbo implementation

`eapburst_turbo.py` is the optimized version of the original `eapburst.py`. It keeps the same command-line model, bounded attempt queue, and one-worker-per-interface design.

The speed improvement comes from three changes:

1. The default per-attempt wait is reduced from `4.5` seconds to `1.5` seconds.
2. Interface state is polled every `0.02` seconds instead of every `0.05` seconds.
3. After authentication has started, the worker exits early when the supplicant reports a failed state (`disconnected`, `inactive`, `interface_disabled`, or `unknown`) instead of waiting for the complete timeout.

The original implementation only checked for `completed` and otherwise continued until its timeout. The turbo version therefore avoids waiting on failures that the supplicant has already exposed. The `0.25`-second default inter-attempt delay is also lower than the original `0.5` seconds.

These changes reduce waiting time; they do not bypass WPA, PEAP, MSCHAPv2, RADIUS policy, account lockout, or access-control mechanisms. The actual rate remains dependent on the supplicant, AP, RADIUS server, driver, and configured delay.

| Setting | `eapburst.py` | `eapburst_turbo.py` |
| --- | ---: | ---: |
| `-t` delay | `0.5 s` | `0.25 s` |
| `--max-wait` | `4.5 s` | `1.5 s` |
| `--test-interval` | `0.05 s` | `0.02 s` |

With three interfaces and a 10,000-attempt workload, the turbo defaults have a theoretical timeout-bound of approximately `10,000 × (1.5 + 0.25) ÷ 3`, or about 1 hour 37 minutes. The observed time can be lower when failures are reported promptly, or higher when the AP/RADIUS server delays responses or rate-limits requests.

## Requirements

- One or more supported wireless interfaces.
- Python 3 matching the target system.
- System `wpa_supplicant` installed and accessible through D-Bus.
- Compatible Python packages: `twisted`, `wpa_supplicant`, `txdbus`, `service_identity`, `cryptography`, `pyOpenSSL`, and `click`.

## Online installation

```bash
python3 -m pip install twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL click
```

If the distribution reports an externally managed Python environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install twisted wpa_supplicant txdbus service_identity cryptography pyOpenSSL click
```

## Offline installation

The repository includes three helper scripts:

- `check_machine_info.sh` collects the target Python version, architecture, and glibc information.
- `build_wheels.sh` creates a dependency bundle on a connected Linux builder.
- `install_wheels.sh` installs the bundle into a local directory on the offline target.

### 1. Collect target information

Run this on the offline target from the repository directory:

```bash
chmod +x check_machine_info.sh build_wheels.sh install_wheels.sh
./check_machine_info.sh
```

This creates `target-info.txt`. Transfer that file and the repository scripts to a connected Linux builder. The builder should use the same Python minor version, CPU architecture, and a compatible glibc baseline as the target.

### 2. Build the wheel bundle

On the connected builder, keep `target-info.txt` beside the scripts and run:

```bash
./build_wheels.sh
```

This creates `wheels.zip`. The script downloads compatible dependencies and builds required source packages locally where necessary.

### 3. Install on the offline target

Transfer `wheels.zip` and `install_wheels.sh` back to the target, place them in the same directory, and run:

```bash
./install_wheels.sh
```

The packages are installed under `./eapburst-libs`, not globally. Set `PYTHONPATH` when running EAPBurst:

```bash
PYTHONPATH=./eapburst-libs python3 ./eapburst.py --help
PYTHONPATH=./eapburst-libs python3 ./eapburst_turbo.py --help
```

Verify compatibility before building:

```bash
python3 --version
uname -m
ldd --version | head -n 1
```

Native wheels must match the target interpreter and platform. A bundle built with a different Python minor version, architecture, or incompatible glibc baseline may not install or import correctly.

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
-s INDEX            Start at this zero-based nonempty username index
-w OUTFILE          Write accepted credentials to CSV
-1                  Stop after the first accepted credential
-t SECONDS          Delay between attempts per worker
--max-wait SECONDS  Maximum wait for each authentication attempt
--test-interval SEC Polling interval while waiting for authentication state
```

Use exactly one of `-P` or `-p`. Each interface runs one worker. By default, all username/password combinations are tested. Use `-1` to stop after the first successful authentication; attempts already running on other interfaces may finish before shutdown.

When using a password list, `-s` applies the selected username index to every password. It does not restore a saved password-list position.

The turbo script accepts the same options:

```bash
PYTHONPATH=./eapburst-libs python3 eapburst_turbo.py \
  -i wlan0,wlan1,wlan2 \
  -e 'Test-Network' \
  -u users.txt \
  -p passwords.txt \
  -w results.csv \
  -1
```

For a first controlled test, use a small password file and a conservative delay:

```bash
python3 eapburst_turbo.py \
  -i wlan0 \
  -e 'Test-Network' \
  -u users.txt \
  -P 'ExamplePassword' \
  --max-wait 2.5 \
  -t 0.5 \
  -1
```

## Inspecting the EAPOL exchange

Capture EAPOL traffic on the interface before running one controlled attempt. The `ether proto 0x888e` filter selects EAPOL frames and `-tttt` prints readable timestamps:

```bash
sudo tcpdump -i wlan0 -nn -tttt -vvv 'ether proto 0x888e'
```

To save a capture for Wireshark:

```bash
sudo tcpdump -i wlan0 -nn -s 0 -w eapol-handshake.pcap 'ether proto 0x888e'
```

Stop `tcpdump` with `Ctrl-C`. In Wireshark, use the display filter:

```text
eapol
```

Compare the timestamps of the EAP request, the client response, and the EAP Failure or EAP Success frame. A managed interface may not expose every over-the-air exchange on every driver; use the appropriate monitor interface when necessary.

## Notes and operational safety

- Authentication attempts can trigger account lockouts, RADIUS throttling, and security alerts.
- Keep the attempt rate and interface count within the approved scope.
- Coordinate testing with the network owner or SOC.
- Treat username lists, terminal output, captures, and CSV files as sensitive data.
- Validate timeout and delay values with a small controlled run before scaling up.

## Disclaimer

For educational and authorized security testing only. Use EAPBurst only against networks and accounts for which you have explicit permission. The authors assume no liability for unauthorized use, account lockouts, service disruption, or other misuse.

## Author

💀 **B5null**
