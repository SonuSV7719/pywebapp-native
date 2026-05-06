"""
Shared utilities for PyWebApp build scripts.
Consolidates common functions used across build_android, dev_sync, and other scripts
to eliminate DRY violations and ensure consistent behavior.
"""

import os
import subprocess
import sys


def get_android_tool(tool_name: str) -> str:
    """Find adb or emulator in PATH or common SDK locations."""
    from shutil import which
    path = which(tool_name)
    if path:
        return path
    if os.name == 'nt':
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(local_app_data, "Android", "Sdk", "platform-tools", f"{tool_name}.exe"),
            os.path.join(local_app_data, "Android", "Sdk", "emulator", f"{tool_name}.exe"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
    return tool_name


def handle_no_devices() -> bool:
    """Search for emulators and offer to start one."""
    print("🔎 Searching for available emulators...")
    emulator_cmd = get_android_tool("emulator")
    try:
        result = subprocess.run([emulator_cmd, "-list-avds"], capture_output=True, text=True, timeout=5)
        avds = [line.strip() for line in result.stdout.split('\n') if line.strip()]
    except Exception:
        avds = []

    if not avds:
        print("   No emulators found. Please connect a device or start an emulator manually.")
        return False

    print("\n📱 Available Emulators:")
    for i, avd in enumerate(avds):
        print(f"  [{i+1}] {avd}")
    print("  [q] Quit")

    choice = input("\n👉 Select an emulator to start (or q): ").strip().lower()
    if choice == 'q':
        return False
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(avds):
            target_avd = avds[idx]
            print(f"\n🚀 Starting emulator: {target_avd}...")
            subprocess.Popen(
                [emulator_cmd, "-avd", target_avd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            print("⏳ Waiting for device to connect...")
            adb_cmd = get_android_tool("adb")
            subprocess.run([adb_cmd, "wait-for-device"], timeout=60)
            print("✅ Device connected!")
            return True
    except (ValueError, IndexError, subprocess.TimeoutExpired):
        print("❌ Failed to start or connect to emulator.")
    return False


def get_project_root() -> str:
    """Search upwards for pywebapp.json to find the project anchor."""
    current = os.getcwd()
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "pywebapp.json")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()
