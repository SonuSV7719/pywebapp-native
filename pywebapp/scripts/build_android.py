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

def sync_python_files():
    """
    Copy all backend Python files to Android's python source directory.
    Rewrites relative package imports to flat imports for Chaquopy compatibility.
    """
    print("\n📋 Syncing Python files to Android...")

    os.makedirs(ANDROID_PYTHON_DIR, exist_ok=True)

    # 🧹 CLEANUP: Remove old synced files to prevent "ghost" file conflicts
    # (e.g. an old handlers.py file blocking a new handlers/ folder)
    print("  🧹 Cleaning old Python files...")
    for item in os.listdir(ANDROID_PYTHON_DIR):
        item_path = os.path.join(ANDROID_PYTHON_DIR, item)
        # Don't delete standard framework files yet, they will be updated in _sync_core_files
        if item not in ["api.py", "context.py", "logger.py", "registry.py"]:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    if not os.path.exists(BACKEND_DIR):
        print(f"  ⚠️  Backend directory not found: {BACKEND_DIR}")
        return

    # Sync all .py files from the backend directory (recursive)
    for root, dirs, files in os.walk(BACKEND_DIR):
        for filename in files:
            if not filename.endswith(".py"):
                continue
                
            src = os.path.join(root, filename)
            
            # Calculate relative path to maintain structure
            rel_path = os.path.relpath(src, BACKEND_DIR)
            dst = os.path.join(ANDROID_PYTHON_DIR, rel_path)
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dst), exist_ok=True)

        with open(src, "r", encoding="utf-8") as f:
            content = f.read()

        # Rewrite relative imports for Chaquopy flat structure
        # `from .module import X` -> `from module import X`
        content = re.sub(r"from \.([a-zA-Z0-9_]+) import", r"from \1 import", content)
        
        # `from . import module` -> `import module`
        content = re.sub(r"from \. import ([a-zA-Z0-9_]+)", r"import \1", content)
        
        # `from . import module as alias` -> `import module as alias`
        content = re.sub(r"from \. import ([a-zA-Z0-9_]+ as [a-zA-Z0-9_]+)", r"import \1", content)

        # Rewrite pywebapp.core imports to flat imports for Chaquopy
        # This handles combined imports like `from pywebapp.core import register, get_logger`
        # by splitting them into `from registry import register` and `from logger import get_logger`.
        if "from pywebapp.core import" in content:
            core_match = re.search(r"from pywebapp\.core import (.+)", content)
            if core_match:
                import_list = [i.strip() for i in core_match.group(1).split(",")]
                flat_imports = []
                for item in import_list:
                    # Clean up any "as alias" parts for mapping
                    base_item = item.split(" as ")[0].strip()
                    
                    if base_item in ["register", "method_registry"]:
                        flat_imports.append(f"from registry import {item}")
                    elif base_item in ["get_logger"]:
                        flat_imports.append(f"from logger import {item}")
                    elif base_item in ["get_context", "set_context", "_set_ctx", "_get_ctx"]:
                        flat_imports.append(f"from context import {item}")
                    elif base_item in ["dispatch", "dispatch_json", "list_methods", "get_schema"]:
                        flat_imports.append(f"from api import {item}")
                    else:
                        # Fallback to registry if unknown
                        flat_imports.append(f"from registry import {item}")
                
                content = content.replace(core_match.group(0), "\n".join(flat_imports))

        # Also handle specific submodule imports
        content = re.sub(r"from pywebapp\.core\.registry import", "from registry import", content)
        content = re.sub(r"from pywebapp\.core\.logger import", "from logger import", content)
        content = re.sub(r"from pywebapp\.core\.context import", "from context import", content)
        content = re.sub(r"from pywebapp\.core\.api import", "from api import", content)

        # Add header comment
        header = f'"""\nAndroid-side copy of backend/{filename}\nAuto-synced by pywebapp build — DO NOT EDIT DIRECTLY.\nSource of truth: backend/{filename}\n"""\n\n'

        # Only add header if not already present
        if "Auto-synced by pywebapp build" not in content:
            content = header + content

        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  ✅ {filename} → android/...python/{filename}")

    # Also sync the core framework files needed on Android
    _sync_core_files()

    print("✅ Python files synced")


def _sync_core_files():
    """Sync pywebapp.core files to Android for Chaquopy compatibility."""
    try:
        import pywebapp.core
        core_dir = os.path.dirname(pywebapp.core.__file__)
    except ImportError:
        print("  ⚠️  pywebapp.core not found, skipping core sync")
        return

    core_files = ["registry.py", "api.py", "context.py", "logger.py"]
    for filename in core_files:
        src = os.path.join(core_dir, filename)
        dst = os.path.join(ANDROID_PYTHON_DIR, filename)

        if not os.path.exists(src):
            continue

        # Only sync if user hasn't provided their own version
        user_version = os.path.join(BACKEND_DIR, filename)
        if os.path.exists(user_version):
            continue

        with open(src, "r", encoding="utf-8") as f:
            content = f.read()

        # Rewrite imports for flat structure
        content = re.sub(r"from pywebapp\.core import context", "import context", content)
        content = re.sub(r"from pywebapp\.core import api", "import api", content)
        content = re.sub(r"from pywebapp\.core import logger", "import logger", content)
        content = re.sub(r"from pywebapp\.core import registry", "import registry", content)
        content = re.sub(r"from pywebapp\.core\.", "from ", content)
        content = re.sub(r"from \.", "from ", content)

        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  ✅ [core] {filename} → android/...python/{filename}")


def build_frontend_for_android():
    """Build frontend and copy to Android assets."""
    from pywebapp.scripts.build_frontend import main as build_frontend_main
    sys.argv = [sys.argv[0], "--copy-to-android"]
    build_frontend_main()


def build_apk():
    """Run Gradle assembleDebug."""
    print("\n🔨 Building Android APK...")

    gradle_cmd = "gradlew.bat" if sys.platform == "win32" else "./gradlew"
    gradle_path = os.path.join(ANDROID_DIR, gradle_cmd)

    if not os.path.exists(gradle_path):
        print(f"⚠️  Gradle wrapper not found at {gradle_path}")
        print("   Open the android/ folder in Android Studio to generate it,")
        print("   or run: cd android && gradle wrapper")
        return

    result = subprocess.run(
        [gradle_path, "assembleDebug"],
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


def main():
    parser = argparse.ArgumentParser(description="Build Android application")
    parser.add_argument("--sync-only", action="store_true", help="Only sync Python files")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build")
    args = parser.parse_args()

    # Always sync Python files
    sync_python_files()

    if args.sync_only:
        return

    # Build frontend
    if not args.skip_frontend:
        build_frontend_for_android()

    # Build APK
    build_apk()


if __name__ == "__main__":
    main()
