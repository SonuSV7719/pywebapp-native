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
import re
import time
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

    # Step 4: Sync Web Icon
    _sync_web_icon()

def _sync_web_icon():
    """Copy the app icon to dist/ and inject it into index.html."""
    import json
    config_path = os.path.join(PROJECT_ROOT, "pywebapp.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            icon_rel_path = config.get("icon_path")
            app_name = config.get("app_name")
    except Exception:
        return

    if not icon_rel_path:
        return

    icon_src = os.path.join(PROJECT_ROOT, icon_rel_path)
    if not os.path.exists(icon_src):
        return

    print(f"\n🌐 Syncing Web Icon: {icon_rel_path}...")
    
    # 1. Copy to dist
    icon_ext = os.path.splitext(icon_rel_path)[1]
    shutil.copy2(icon_src, os.path.join(DIST_DIR, f"favicon{icon_ext}"))
    
    # 2. ⚡ Sync to frontend/public for Dev Mode (Vite)
    public_dir = os.path.join(FRONTEND_DIR, "public")
    if os.path.exists(public_dir):
        shutil.copy2(icon_src, os.path.join(public_dir, f"favicon{icon_ext}"))

    # 3. Inject into index.html (both dist and source)
    target_files = [
        os.path.join(DIST_DIR, "index.html"),
        os.path.join(FRONTEND_DIR, "index.html")
    ]
    
    now = int(time.time())
    for index_path in target_files:
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                html = f.read()
            
            # 🧪 Sync Icon with Cache Buster
            if 'rel="icon"' not in html:
                icon_tag = f'\n    <link rel="icon" type="image/png" href="favicon{icon_ext}?v={now}">'
                html = html.replace('</head>', f'{icon_tag}\n</head>')
            else:
                html = re.sub(r'href="favicon.*?\?v=\d+"', f'href="favicon{icon_ext}?v={now}"', html)
            
            # 🏷️ Sync App Name (Title)
            if app_name:
                if '<title>' in html:
                    html = re.sub(r'<title>.*?</title>', f'<title>{app_name}</title>', html)
                else:
                    title_tag = f'\n    <title>{app_name}</title>'
                    html = html.replace('</head>', f'{title_tag}\n</head>')

            with open(index_path, "w", encoding="utf-8") as f:
                f.write(html)
        
    print(f"✅ Web assets (Dev & Prod) synced")


if __name__ == "__main__":
    main()
