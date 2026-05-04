#!/usr/bin/env python3
"""
Build script for the React frontend.

Usage:
    python -m pywebapp.scripts.build_frontend
    python -m pywebapp.scripts.build_frontend --copy-to-android

Steps:
    1. Runs `npm install` in frontend/
    2. Runs `npm run build` to produce dist/
    3. Optionally copies dist/ to android/app/src/main/assets/web/
"""

import argparse
import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.getcwd()
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
ANDROID_ASSETS_DIR = os.path.join(
    PROJECT_ROOT, "android", "app", "src", "main", "assets", "web"
)


def run(cmd, cwd=None):
    """Run a shell command and stream output."""
    print(f"\n{'='*60}")
    print(f"  Running: {cmd}")
    print(f"  Directory: {cwd or os.getcwd()}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        cmd, shell=True, cwd=cwd, text=True, capture_output=False
    )

    if result.returncode != 0:
        print(f"\n❌ Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Build React frontend")
    parser.add_argument(
        "--copy-to-android",
        action="store_true",
        help="Copy built files to Android assets directory",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm install (if node_modules exists)",
    )
    args = parser.parse_args()

    # Step 1: npm install
    if not args.skip_install:
        run("npm install", cwd=FRONTEND_DIR)
    else:
        print("⏭️  Skipping npm install")

    # Step 2: npm run build
    run("npm run build", cwd=FRONTEND_DIR)

    # Verify build output
    index_file = os.path.join(DIST_DIR, "index.html")
    if not os.path.exists(index_file):
        print("❌ Build failed — dist/index.html not found")
        sys.exit(1)

    print(f"\n✅ Frontend built successfully → {DIST_DIR}")

    # Step 3: Copy to Android assets (optional)
    if args.copy_to_android:
        print(f"\n📱 Copying to Android assets: {ANDROID_ASSETS_DIR}")

        # Remove old assets
        if os.path.exists(ANDROID_ASSETS_DIR):
            shutil.rmtree(ANDROID_ASSETS_DIR)

        # Copy new build
        shutil.copytree(DIST_DIR, ANDROID_ASSETS_DIR)
        print("✅ Copied to Android assets")


if __name__ == "__main__":
    main()
