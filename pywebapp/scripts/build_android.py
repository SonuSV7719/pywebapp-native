#!/usr/bin/env python3
"""
Build script for the Android application.

Usage:
    python -m pywebapp.scripts.build_android              # Sync Python + build frontend + assemble APK
    python -m pywebapp.scripts.build_android --sync-only  # Only sync Python files to Android
    python -m pywebapp.scripts.build_android --skip-frontend  # Skip frontend rebuild

Steps:
    1. Syncs backend/*.py → android/app/src/main/python/ (with import rewrites)
    2. Builds frontend and copies to android/app/src/main/assets/web/
    3. Runs gradle assembleDebug
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import json

# --- Universal Icon Support ---
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# Resolve paths relative to user's project (Searching for pywebapp.json)
def get_project_root():
    current = os.getcwd()
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "pywebapp.json")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()

PROJECT_ROOT = get_project_root()
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
ANDROID_PYTHON_DIR = os.path.join(
    PROJECT_ROOT, "android", "app", "src", "main", "python"
)
ANDROID_DIR = os.path.join(PROJECT_ROOT, "android")
ANDROID_RES_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "res")

def get_config():
    """Load pywebapp.json and merge platform-specific overrides."""
    config_path = os.path.join(PROJECT_ROOT, "pywebapp.json")
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        # 🟢 Smart Merge: If 'android' block exists, override top-level settings
        android_cfg = config.get("android", {})
        if isinstance(android_cfg, dict):
            for k, v in android_cfg.items():
                config[k] = v
        return config
    except Exception:
        return {}

def sync_app_icons():
    """Update Android launcher icons from pywebapp.json."""
    config = get_config()
    icon_rel_path = config.get("icon_path") or config.get("app_icon")
    if not icon_rel_path:
        print("  ℹ️  No icon found in config, skipping icon sync")
        return

    icon_src = os.path.join(PROJECT_ROOT, icon_rel_path)
    if not os.path.exists(icon_src):
        print(f"  ⚠️  Icon file not found: {icon_src}")
        return

    if not HAS_PILLOW:
        print("  ⚠️  Pillow (PIL) not found. Icons will NOT be processed.")
        return

    print(f"\n🎨 Processing App Icon: {icon_rel_path}...")

    # Android density buckets and their respective icon sizes (48dp base)
    # ldpi: 36, mdpi: 48, hdpi: 72, xhdpi: 96, xxhdpi: 144, xxxhdpi: 192
    densities = {
        "mipmap-mdpi": (48, 48),
        "mipmap-hdpi": (72, 72),
        "mipmap-xhdpi": (96, 96),
        "mipmap-xxhdpi": (144, 144),
        "mipmap-xxxhdpi": (192, 192),
    }

    try:
        with Image.open(icon_src) as img:
            # Ensure we are in RGBA for transparency support
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            for folder, size in densities.items():
                target_dir = os.path.join(ANDROID_RES_DIR, folder)
                os.makedirs(target_dir, exist_ok=True)
                
                # 1. Standard Square Icon
                target_path = os.path.join(target_dir, "ic_launcher.png")
                # 2. Round Icon (Modern Android standard)
                target_round_path = os.path.join(target_dir, "ic_launcher_round.png")
                
                # High-quality resize and save both
                resized_img = img.resize(size, Image.Resampling.LANCZOS)
                resized_img.save(target_path, "PNG")
                resized_img.save(target_round_path, "PNG")
                
                # 3. Clean up Adaptive XMLs/WebP that might hijack our PNGs
                for ext in [".xml", ".webp"]:
                    for base in ["ic_launcher", "ic_launcher_round"]:
                        junk = os.path.join(target_dir, f"{base}{ext}")
                        if os.path.exists(junk):
                            os.remove(junk)
                
                print(f"  ✅ Updated {folder} (Square + Round)")
                
    except Exception as e:
        print(f"  ❌ Failed to process icons: {e}")

def sync_splash_screen():
    """Generate and sync splash screen resources."""
    config = get_config()
    splash_rel_path = config.get("splash_image")
    if not splash_rel_path:
        return

    splash_src = os.path.join(PROJECT_ROOT, splash_rel_path)
    if not os.path.exists(splash_src) or not HAS_PILLOW:
        return

    print(f"✨ Generating Splash Screen from: {splash_rel_path}...")
    
    try:
        from PIL import Image
        with Image.open(splash_src) as img:
            # We save a high-res version for the splash center
            dst_dir = os.path.join(ANDROID_RES_DIR, "drawable")
            os.makedirs(dst_dir, exist_ok=True)
            
            # Save as splash_logo.png
            target_path = os.path.join(dst_dir, "splash_logo.png")
            
            # If icon mode is not RGBA, convert it
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Ensure it fits nicely (max 512x512 for the logo part)
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            img.save(target_path, "PNG")
            print("  ✅ Splash Logo generated at drawable/splash_logo.png")
    except Exception as e:
        print(f"  ❌ Failed to generate splash: {e}")

def sync_python_files():
    """
    Copy all backend Python files to Android's python source directory.
    Maintains full package structure for reliable imports.
    """
    print("\n📋 Syncing Python files to Android...")

    os.makedirs(ANDROID_PYTHON_DIR, exist_ok=True)

    # 🧹 CLEANUP: Remove old synced files to prevent conflicts
    print("  🧹 Cleaning old Python files...")
    for item in ["api.py", "context.py", "logger.py", "registry.py", "backend", "pywebapp"]:
        item_path = os.path.join(ANDROID_PYTHON_DIR, item)
        if os.path.exists(item_path):
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    if not os.path.exists(BACKEND_DIR):
        print(f"  ⚠️  Backend directory not found: {BACKEND_DIR}")
        return

    # Ensure backend package exists
    android_backend_dir = os.path.join(ANDROID_PYTHON_DIR, "backend")
    os.makedirs(android_backend_dir, exist_ok=True)
    
    # Sync all files from backend/ maintaining structure
    for root, dirs, files in os.walk(BACKEND_DIR):
        # ⚡ Auto-Package: Ensure every sub-folder has an __init__.py
        rel_root = os.path.relpath(root, BACKEND_DIR)
        dst_root = os.path.join(android_backend_dir, rel_root)
        os.makedirs(dst_root, exist_ok=True)
        
        init_file = os.path.join(dst_root, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Auto-generated by PyWebApp\n")

        for filename in files:
            src = os.path.join(root, filename)
            rel_path = os.path.relpath(src, BACKEND_DIR)
            dst = os.path.join(android_backend_dir, rel_path)
            
            shutil.copy2(src, dst)
            print(f"  ✅ [backend] {rel_path} → android/.../backend/{rel_path}")

    # Also sync the core framework files
    _sync_core_files()

    # Sync Splash Screen if configured
    sync_splash_screen()

    print("✅ Python environment prepared")


def _sync_core_files():
    """Sync pywebapp.core files to Android inside a proper package structure."""
    try:
        import pywebapp
        framework_dir = os.path.dirname(pywebapp.__file__)
    except ImportError:
        print("  ⚠️  pywebapp package not found, skipping core sync")
        return

    print("  📦 Syncing Framework Core to APK...")
    
    # 🚀 Total Sync: Push everything inside the pywebapp package folder
    target_framework_dir = os.path.join(ANDROID_PYTHON_DIR, "pywebapp")
    os.makedirs(target_framework_dir, exist_ok=True)
    
    for item in os.listdir(framework_dir):
        # Skip pycache and temp files
        if item.startswith("__pycache__") or item.endswith(".pyc") or item.startswith("."):
            continue
            
        src_item = os.path.join(framework_dir, item)
        dst_item = os.path.join(target_framework_dir, item)
        
        if os.path.isdir(src_item):
            # Check if it's a python package (has __init__.py)
            if os.path.exists(os.path.join(src_item, "__init__.py")):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
                print(f"  ✅ [core] package: {item} → android/.../pywebapp/{item}")
        elif item == "__init__.py":
            shutil.copy2(src_item, dst_item)
            print(f"  ✅ [core] file: {item} → android/.../pywebapp/{item}")


def build_frontend_for_android():
    """Build frontend and copy to Android assets."""
    from pywebapp.scripts.build_frontend import main as build_frontend_main
    sys.argv = [sys.argv[0], "--copy-to-android"]
    build_frontend_main()


def build_apk(clean=False):
    """Run Gradle assembleDebug."""
    print("\n🔨 Building Android APK...")
    if clean:
        print("🧼 Performing clean build...")

    gradle_cmd = "gradlew.bat" if sys.platform == "win32" else "./gradlew"
    gradle_path = os.path.join(ANDROID_DIR, gradle_cmd)

    if not os.path.exists(gradle_path):
        print(f"⚠️  Gradle wrapper not found at {gradle_path}")
        print("   Open the android/ folder in Android Studio to generate it,")
        print("   or run: cd android && gradle wrapper")
        return

    # Build the task list
    tasks = ["assembleDebug"]
    if clean:
        tasks.insert(0, "clean")

    result = subprocess.run(
        [gradle_path] + tasks,
        cwd=ANDROID_DIR,
    )

    if result.returncode != 0:
        print("❌ Gradle build failed")
        sys.exit(result.returncode)

    apk_path = os.path.join(
        ANDROID_DIR, "app", "build", "outputs", "apk", "debug", "app-debug.apk"
    )
    if os.path.exists(apk_path):
        print(f"\n✅ APK built: {apk_path}")
    else:
        print("\n⚠️  APK not found at expected location")




# 🔧 P2: Shared utilities (consolidated from duplicate definitions)
from pywebapp.scripts.utils import get_android_tool, handle_no_devices

def install_apk(device=None):
    """Install the built APK on the connected device. Launches emulator if needed."""
    apk_path = os.path.join(
        ANDROID_DIR, "app", "build", "outputs", "apk", "debug", "app-debug.apk"
    )
    if not os.path.exists(apk_path):
        # Check if it might be a release build calling this
        apk_path = os.path.join(ANDROID_DIR, "app", "build", "outputs", "apk", "release", "app-release.apk")
        
    if not os.path.exists(apk_path):
        print(f"❌ APK not found for installation.")
        return False
    
    # Check for connected devices first
    adb = get_android_tool("adb")
    result = subprocess.run([adb, "devices"], capture_output=True, text=True)
    connected = [l for l in result.stdout.strip().split('\n')[1:] if 'device' in l and 'offline' not in l]
    
    if not connected:
        print("\n❌ No Android device connected.")
        if not handle_no_devices():
            return False

    print("\n📲 Installing APK to device...")
    cmd = [adb]
    if device:
        cmd += ["-s", device]
    cmd += ["install", "-r", apk_path]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ APK installed successfully")
        return True
    else:
        print(f"❌ Installation failed: {result.stderr or result.stdout}")
        return False


def sync_app_name():
    """Update the Android app name in strings.xml based on pywebapp.json."""
    config_path = os.path.join(PROJECT_ROOT, "pywebapp.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            app_name = config.get("app_name")
    except Exception:
        return

    if not app_name:
        return

    strings_path = os.path.join(ANDROID_RES_DIR, "values", "strings.xml")
    if not os.path.exists(strings_path):
        return

    print(f"🏷️  Updating Android App Name to: '{app_name}'")
    
    with open(strings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex to find <string name="app_name">...</string>
    new_content = re.sub(
        r'<string name="app_name">.*?</string>',
        f'<string name="app_name">{app_name}</string>',
        content
    )

    if new_content != content:
        with open(strings_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("  ✅ strings.xml updated")

def sync_app_id():
    """Update the Android applicationId in build.gradle.kts based on pywebapp.json."""
    config = get_config()
    app_id = config.get("app_id")
    
    if not app_id:
        return

    gradle_path = os.path.join(ANDROID_DIR, "app", "build.gradle.kts")
    if not os.path.exists(gradle_path):
        return

    try:
        with open(gradle_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find applicationId = "..."
        new_content = re.sub(
            r'applicationId\s*=\s*".*?"',
            f'applicationId = "{app_id}"',
            content
        )

        if new_content != content:
            print(f"🏷️  Updating Android Application ID to: '{app_id}'")
            with open(gradle_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("  ✅ build.gradle.kts updated")
    except Exception as e:
        print(f"  ❌ Failed to sync App ID: {e}")

def main():
    parser = argparse.ArgumentParser(description="Build Android application")
    parser.add_argument("--sync-only", action="store_true", help="Only sync Python files")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    parser.add_argument("--clean", action="store_true", help="Perform clean build")
    parser.add_argument("--install", action="store_true", help="Install APK to device after build")
    args = parser.parse_args()

    config = get_config()

    # Always sync Python files
    sync_python_files()

    # Sync App Icons (Android Mipmaps)
    sync_app_icons()

    # Sync App Name (strings.xml)
    sync_app_name()
    
    # Sync App ID (build.gradle.kts)
    sync_app_id()

    if args.sync_only:
        return

    # Build frontend
    if not args.skip_frontend:
        build_frontend_for_android()

    # Build APK
    build_apk(clean=args.clean)

    # Install if requested
    if args.install:
        install_apk()


if __name__ == "__main__":
    main()
