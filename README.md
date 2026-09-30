# EAPBurst

EAPBurst is a Python 3 WPA Enterprise credential validation tool for
authorized wireless assessments. It performs online PEAP/MSCHAPv2 authentication
attempts against a target SSID and can distribute attempts across multiple
wireless interfaces.

## Concurrency model

Each wireless interface can handle one association attempt at a time. For that
reason, concurrency is controlled directly by the interface list passed to `-i`.
Supplying one interface runs one worker; supplying two interfaces runs two
workers.

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -P UserPassword1 -u usernames.txt
```

## Dependencies

Install the Python runtime dependencies:

```bash
pip3 install twisted wpa_supplicant
```

The host must also have working wireless interfaces and access to
`wpa_supplicant` over D-Bus.

## Usage

```text
usage: eapburst.py [-h] -i interface[,interface...] -e SSID -u USERFILE
                     [-P PASSWORD] [-p PASSFILE] [-s line] [-w OUTFILE] [-1]
                     [-t seconds] [--max-wait seconds]
                     [--test-interval seconds]

Perform an online, horizontal dictionary attack against a WPA Enterprise
network.
```

Options:

```text
-i interface[,interface...]
                      Wireless interface, or comma-separated interfaces for
                      concurrent attempts
-e SSID               SSID of the target network
-u USERFILE           Username wordlist
-P PASSWORD           Password to try on each username
-p PASSFILE           List of passwords to try for each username
-s line               Optional start line to resume attack. May not be used
                      with a password list.
-w OUTFILE            Save valid credentials to a CSV file
-1                    Stop after the first set of valid credentials are found
-t seconds            Seconds to sleep between each connection attempt per
                      worker
--max-wait seconds    Maximum seconds to wait for a successful association per
                      attempt
--test-interval seconds
                      Polling interval while waiting for association state
```

## Examples

Single-interface run:

```bash
python3 ./eapburst.py -i wlan0 -e Test-Network -P UserPassword1 -u usernames.txt
```

Two-interface concurrent run:

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -P UserPassword1 -u usernames.txt
```

Password-list run:

```bash
python3 ./eapburst.py -i wlan0,wlan1 -e Test-Network -p passwords.txt -u usernames.txt
```

Resume at username line 250 with a single password:

```bash
python3 ./eapburst.py -i wlan0 -e Test-Network -P UserPassword1 -u usernames.txt -s 250
```
