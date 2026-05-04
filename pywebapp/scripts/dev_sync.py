#!/usr/bin/env python3
"""
Development Sync Server for Android hot reload.

Watches backend/ for Python file changes and pushes them to a connected
Android device/emulator via ADB. Then triggers a module reload on the device.

Architecture:
    Dev Machine                         Android Device
    ──────────                         ──────────────
    watchdog watches backend/    →     adb push files to /data/local/tmp/pywebapp/
    detects .py change           →     trigger reload via adb broadcast
                                       Python: importlib.reload() on modules

Usage (dev mode only):
    python -m pywebapp.scripts.dev_sync                    # Watch + sync + reload
    python -m pywebapp.scripts.dev_sync --push-only        # One-time push, no watch
    python -m pywebapp.scripts.dev_sync --device 192.168.1.5:5555  # Specific device

Prerequisites:
    - ADB in PATH
    - Device/emulator connected
    - App running in dev mode (DEV_MODE=true)
"""

import argparse
import os
import re
import subprocess
import sys
import time
import threading

PROJECT_ROOT = os.getcwd()
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

# Where Python files are pushed on the Android device
DEVICE_PYTHON_DIR = "/data/local/tmp/pywebapp/python"

# Files to sync
SYNC_FILES = ["registry.py", "api.py", "handlers.py", "logger.py", "__init__.py"]

# Debounce
DEBOUNCE_SECONDS = 0.5


def run_adb(args, device=None):
    """Run an ADB command and return (success, output)."""
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += args

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def check_adb_connection(device=None):
    """Check if ADB is available and a device is connected."""
    success, output = run_adb(["devices"], device)
    if not success:
        print("❌ ADB not found. Make sure Android SDK platform-tools is in PATH.")
        return False

    lines = output.strip().split('\n')
    connected = [l for l in lines[1:] if 'device' in l and 'offline' not in l]

    if not connected:
        print("❌ No Android device/emulator connected.")
        print("   Start an emulator or connect a device via USB.")
        return False

    print(f"✅ Connected devices: {len(connected)}")
    for line in connected:
        print(f"   {line}")
    return True


def push_python_files(device=None, rewrite_imports=True):
    """Push backend Python files to the device."""
    # Create target directory on device
    run_adb(["shell", "mkdir", "-p", DEVICE_PYTHON_DIR], device)

    pushed = []
    for filename in SYNC_FILES:
        src = os.path.join(BACKEND_DIR, filename)
        if not os.path.exists(src):
            continue

        dst = f"{DEVICE_PYTHON_DIR}/{filename}"

        if rewrite_imports:
            # Read, rewrite imports, push via stdin
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()

            # Rewrite relative imports for flat structure
            content = re.sub(r"from \.", "from ", content)

            # Rewrite pywebapp.core imports
            content = re.sub(r"from pywebapp\.core\.", "from ", content)
            content = re.sub(r"from pywebapp\.core import", "from registry import", content)

            # Write to temp file, then push
            temp_dir = os.path.join(PROJECT_ROOT, ".pywebapp_tmp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f".tmp_{filename}")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)

            success, output = run_adb(["push", temp_path, dst], device)
            os.remove(temp_path)
        else:
            success, output = run_adb(["push", src, dst], device)

        if success:
            pushed.append(filename)
            print(f"  📦 {filename} → {dst}")
        else:
            print(f"  ❌ Failed to push {filename}: {output}")

    return pushed


def trigger_reload(device=None):
    """
    Trigger Python module reload on the running app.
    Sends a broadcast intent that the app's DevReceiver picks up.
    """
    success, output = run_adb(
        [
            "shell", "am", "broadcast",
            "-a", "com.example.pywebapp.RELOAD_PYTHON",
            "-n", "com.example.pywebapp/.dev.DevReloadReceiver",
        ],
        device,
    )
    if success:
        print("  🔄 Reload signal sent to app")
    else:
        print(f"  ⚠️  Reload signal failed (app may not be in dev mode): {output}")


def push_and_reload(device=None):
    """Push files and trigger reload."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"\n[{timestamp}] ♻️  Change detected — syncing...")

    pushed = push_python_files(device)
    if pushed:
        trigger_reload(device)
        print(f"  ✅ Synced {len(pushed)} file(s)")
    else:
        print("  ⚠️  No files to sync")


def watch_and_sync(device=None):
    """Watch backend/ for changes and sync to device."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("❌ watchdog not installed. Run: pip install watchdog")
        sys.exit(1)

    debounce_timer = None
    lock = threading.Lock()

    class SyncHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory or not event.src_path.endswith('.py'):
                return

            nonlocal debounce_timer
            with lock:
                if debounce_timer:
                    debounce_timer.cancel()
                debounce_timer = threading.Timer(
                    DEBOUNCE_SECONDS,
                    push_and_reload,
                    kwargs={"device": device},
                )
                debounce_timer.daemon = True
                debounce_timer.start()

    observer = Observer()
    observer.schedule(SyncHandler(), BACKEND_DIR, recursive=True)
    observer.start()

    print(f"\n🔥 Dev Sync active — watching: {BACKEND_DIR}")
    print(f"   Syncing to device: {device or '(default)'}")
    print(f"   Target: {DEVICE_PYTHON_DIR}")
    print("   Press Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Dev sync stopped")
    observer.join()


def setup_adb_reverse(port=5173, device=None):
    """Setup ADB reverse port forwarding for Vite dev server."""
    success, output = run_adb(
        ["reverse", f"tcp:{port}", f"tcp:{port}"],
        device,
    )
    if success:
        print(f"✅ ADB reverse: device:{port} → localhost:{port}")
    else:
        print(f"❌ ADB reverse failed: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="PyWebApp Android Dev Sync — Hot reload for Android"
    )
    parser.add_argument(
        "--push-only",
        action="store_true",
        help="Push files once without watching",
    )
    parser.add_argument(
        "--device", "-s",
        type=str,
        default=None,
        help="Target device serial (from 'adb devices')",
    )
    parser.add_argument(
        "--setup-reverse",
        action="store_true",
        help="Setup ADB reverse port forwarding for Vite dev server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5173,
        help="Vite dev server port (default: 5173)",
    )
    args = parser.parse_args()

    print("🤖 PyWebApp Android Dev Sync")
    print("=" * 40)

    # Check ADB connection
    if not check_adb_connection(args.device):
        sys.exit(1)

    # Setup ADB reverse for frontend dev server
    if args.setup_reverse:
        setup_adb_reverse(args.port, args.device)

    if args.push_only:
        # One-time push
        print("\n📦 Pushing Python files to device...")
        pushed = push_python_files(args.device)
        trigger_reload(args.device)
        print(f"\n✅ Done — pushed {len(pushed)} file(s)")
    else:
        # Initial push + watch
        print("\n📦 Initial push...")
        push_python_files(args.device)

        # Setup ADB reverse by default
        setup_adb_reverse(args.port, args.device)

        # Start watching
        watch_and_sync(args.device)


if __name__ == "__main__":
    main()
