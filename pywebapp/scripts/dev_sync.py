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
import hashlib

# Import build scripts for branding sync
from pywebapp.scripts.build_android import sync_app_icons, sync_app_name

PROJECT_ROOT = os.getcwd()
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

# Where Python files are pushed on the Android device
DEVICE_PYTHON_DIR = "/data/local/tmp/pywebapp/python"

# Files to sync
SYNC_FILES = ["registry.py", "api.py", "handlers.py", "logger.py", "__init__.py"]

# Debounce
DEBOUNCE_SECONDS = 0.5


# 🔧 P2: Shared utilities (consolidated from duplicate definitions)
from pywebapp.scripts.utils import get_android_tool, handle_no_devices

def run_adb(args, device=None):
    """Run an ADB command and return (success, output)."""
    adb_cmd = get_android_tool("adb")
    cmd = [adb_cmd]
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
    """Check if ADB is available and a device is connected. Prompt to start emulator if none."""
    success, output = run_adb(["devices"], device)
    if not success:
        print("❌ ADB not found. Make sure Android SDK platform-tools is in PATH.")
        return False

    lines = output.strip().split('\n')
    connected = [l for l in lines[1:] if 'device' in l and 'offline' not in l]

    if not connected:
        print("\n❌ No Android device/emulator connected.")
        return handle_no_devices()

    print(f"✅ Connected devices: {len(connected)}")
    for line in connected:
        print(f"   {line}")
    return True


def push_framework_files(device=None):
    """Push the pywebapp framework's own core files to the device."""
    import pywebapp
    framework_dir = os.path.dirname(pywebapp.__file__)
    
    # 🚀 Total Sync: Push everything inside the pywebapp package folder
    # This includes core, scripts, plugins, and __init__.py
    for item in os.listdir(framework_dir):
        # Skip pycache and temp files
        if item.startswith("__pycache__") or item.endswith(".pyc") or item.startswith("."):
            continue
            
        src_item = os.path.join(framework_dir, item)
        dst_item = f"{DEVICE_PYTHON_DIR}/pywebapp/{item}"
        
        if os.path.isdir(src_item):
            # Check if it's a python package (has __init__.py)
            if os.path.exists(os.path.join(src_item, "__init__.py")):
                run_adb(["shell", "mkdir", "-p", dst_item], device)
                run_adb(["push", src_item + "/.", dst_item], device)
        elif item == "__init__.py":
            run_adb(["push", src_item, dst_item], device)
    
    print("  ✅ Framework All-Modules Synced")


def push_python_files(device=None):
    """Push backend Python files to the device recursively."""
    # First, ensure framework is up to date on device
    push_framework_files(device)

    pushed = []
    # Sync all files from backend/ maintaining structure
    for root, dirs, files in os.walk(BACKEND_DIR):
        # ⚡ Auto-Package: Ensure every sub-folder has an __init__.py on device
        rel_root = os.path.relpath(root, BACKEND_DIR)
        dst_root = f"{DEVICE_PYTHON_DIR}/backend/{rel_root.replace(os.sep, '/')}"
        run_adb(["shell", "mkdir", "-p", dst_root], device)
        
        init_file = f"{dst_root}/__init__.py"
        # We check if it exists on device (cheaper to just push if small)
        run_adb(["shell", f"echo '# Auto-generated' > {init_file}"], device)

        for f in files:
            # Sync .py and common data files
            if f.endswith((".py", ".json", ".csv", ".db", ".sqlite")):
                src = os.path.join(root, f)
                rel_path = os.path.relpath(src, BACKEND_DIR)
                dst = f"{DEVICE_PYTHON_DIR}/backend/{rel_path.replace(os.sep, '/')}"
                
                # Direct push
                success, output = run_adb(["push", src, dst], device)
                if success:
                    pushed.append(rel_path)
                    print(f"  📦 {rel_path} → {dst}")
                else:
                    print(f"  ❌ Failed to push {rel_path}: {output}")

    return pushed


def trigger_reload(device=None):
    """
    Trigger Python module reload on the running app.
    Sends a broadcast intent that the app's DevReceiver picks up.
    """
    # 🔒 P1: Use dynamic package name instead of hardcoded com.example.pywebapp
    base_id, suffix = get_package_name()
    package = f"{base_id}{suffix}"
    
    success, output = run_adb(
        [
            "shell", "am", "broadcast",
            "-a", f"{base_id}.RELOAD_PYTHON",
            "-n", f"{package}/{base_id}.dev.DevReloadReceiver",
        ],
        device,
    )
    if success:
        print("  🔄 Reload signal sent to app")
    else:
        print(f"  ⚠️  Reload signal failed (app may not be in dev mode): {output}")


def get_package_name():
    """Parse build.gradle.kts to find the real applicationId and suffix."""
    gradle_path = os.path.join(PROJECT_ROOT, "android", "app", "build.gradle.kts")
    base_id = "com.example.pywebapp"
    suffix = ""
    
    if os.path.exists(gradle_path):
        try:
            with open(gradle_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Find applicationId = "..."
                id_match = re.search(r'applicationId\s*=\s*"([^"]+)"', content)
                if id_match:
                    base_id = id_match.group(1)
                
                # Find applicationIdSuffix = "..."
                suffix_match = re.search(r'applicationIdSuffix\s*=\s*"([^"]+)"', content)
                if suffix_match:
                    suffix = suffix_match.group(1)
        except Exception:
            pass
            
    return base_id, suffix

def launch_app(device=None):
    """Launch the app on the device/emulator. Installs if missing."""
    base_id, suffix = get_package_name()
    package = f"{base_id}{suffix}"
    
    # 🔍 Check if app is installed
    _, output = run_adb(["shell", "pm", "list", "packages", package], device)
    if package not in output:
        print(f"\n⚠️  App '{package}' not found on device.")
        print("🔨 Starting automated build and installation...")
        from pywebapp.scripts.build_android import build_apk, install_apk
        build_apk()
        if not install_apk(device):
            print("❌ Automated installation failed. Please check your Android setup.")
            return

    # 🚀 Launch using Package ID / Full Class Name
    # We use the base_id for the class path
    activity = f"{package}/{base_id}.MainActivity"
    print(f"🚀 Launching app: {package}...")
    run_adb(["shell", "am", "start", "-n", activity], device)


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
            if event.is_directory:
                return
                
            filename = os.path.basename(event.src_path)
            
            # 🏷️ Handle Branding Sync (pywebapp.json)
            if filename == "pywebapp.json":
                print(f"\n⚙️  Config change detected — syncing branding...")
                sync_app_name()
                sync_app_icons()
                return

            # 🐍 Handle Python Sync
            if not event.src_path.endswith('.py'):
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
    # Watch both backend/ and PROJECT_ROOT (for pywebapp.json)
    observer.schedule(SyncHandler(), BACKEND_DIR, recursive=True)
    observer.schedule(SyncHandler(), PROJECT_ROOT, recursive=False)
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
        
        # Initial branding sync
        sync_app_name()
        sync_app_icons()

        # Setup ADB reverse by default
        setup_adb_reverse(args.port, args.device)

        # 🚀 Auto-launch the app
        launch_app(args.device)

        # Start watching
        watch_and_sync(args.device)


if __name__ == "__main__":
    main()
