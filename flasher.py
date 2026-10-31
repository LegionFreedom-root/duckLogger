#!/usr/bin/env python3
"""
flasher.py - Automates flashing DuckLogger onto a MicroPython board.
Compatible with Windows/Linux/macOS.
Run from the root of the duckLogger directory.
"""

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
MPREMOTE = [sys.executable, "-m", "mpremote"]


def run(args, desc=""):
    print(f"  {desc or ' '.join(args)}")

    result = subprocess.run(
        args,
        text=True,
        capture_output=True
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Command failed:\n" + " ".join(args))


def require_mpremote():
    result = subprocess.run(
        MPREMOTE + ["--version"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "mpremote is not available. "
            "Install it using: python -m pip install mpremote"
        )


def compress(src, dst):
    with open(src, "rb") as fin, gzip.open(dst, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def mp(args):
    return MPREMOTE + args


def step(title):
    print(f"\n\033[32m-- {title}\033[0m")


def wait_for_board():
    """Wait until a MicroPython board is detected."""
    while True:
        result = subprocess.run(
            mp(["exec", "pass"]),
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("  Board detected.")
            return

        input(
            "\nNo board detected. Reconnect ESP32 "
            "and press ENTER to retry..."
        )


def mkdir(remote):
    subprocess.run(
        mp(["mkdir", remote]),
        capture_output=True,
        text=True
    )


def upload_tree(local_root, remote_root):
    """Upload a local directory recursively, preserving its structure."""
    for item in sorted(local_root.rglob("*")):
        rel = item.relative_to(local_root)
        remote = remote_root.rstrip("/") + "/" + rel.as_posix()

        if item.is_dir():
            mkdir(remote)
        else:
            run(
                mp(["cp", str(item), remote]),
                f"Copy {rel}"
            )


def main():
    compressed_file = ROOT / "index.html.gz"

    required_files = [
        ROOT / "index.html",
        ROOT / "settings.json",
        ROOT / "main.py",
        ROOT / "lib"
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    try:
        step("Install mpremote")
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "mpremote"
            ],
            "Installing mpremote"
        )
        require_mpremote()

        step("Detect board")
        wait_for_board()

        step("Install MicroPython packages")
        run(mp(["mip", "install", "usb-device"]), "usb-device")
        run(
            mp(["mip", "install", "usb-device-keyboard"]),
            "usb-device-keyboard"
        )

        step("Compress index.html")
        compress(ROOT / "index.html", compressed_file)
        print("  index.html -> index.html.gz")

        step("Prepare directories")
        mkdir(":/lib")
        mkdir(":/lib/microdot")

        step("Copy files to board")
        upload_tree(ROOT / "lib", ":/lib")

        run(
            mp(["cp", str(compressed_file), ":"]),
            "index.html.gz -> /"
        )
        run(
            mp(["cp", str(ROOT / "settings.json"), ":"]),
            "settings.json -> /"
        )
        run(
            mp(["cp", str(ROOT / "main.py"), ":"]),
            "main.py -> /"
        )

        step("Reboot board")
        run(mp(["reset"]), "Resetting board")

        print("\n========================================")
        print("DuckLogger installed successfully!")
        print("========================================")

    finally:
        compressed_file.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
