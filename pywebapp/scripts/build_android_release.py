#!/usr/bin/env python3
"""
Automated script to build a signed release APK for Android.
This script will:
1. Sync frontend and backend (via build_android.py)
2. Generate a release keystore if it doesn't exist
3. Create keystore.properties if it doesn't exist
4. Run Gradle to build the signed APK

Usage:
    python -m pywebapp.scripts.build_android_release
    python -m pywebapp.scripts.build_android_release --password your_secure_password
"""

import argparse
import os
import subprocess
import sys
import string
import secrets

PROJECT_ROOT = os.getcwd()
ANDROID_DIR = os.path.join(PROJECT_ROOT, "android")
KEYSTORE_FILE = os.path.join(ANDROID_DIR, "app", "pywebapp-release.keystore")
PROPERTIES_FILE = os.path.join(ANDROID_DIR, "keystore.properties")
STRINGS_XML = os.path.join(ANDROID_DIR, "app", "src", "main", "res", "values", "strings.xml")

def update_android_branding():
    """Update Android app name from pywebapp.json."""
    config_path = os.path.join(PROJECT_ROOT, "pywebapp.json")
    if not os.path.exists(config_path):
        return
    
    import json
    import re
    
    with open(config_path, "r") as f:
        config = json.load(f)
        app_name = config.get("app_name")
        if not app_name:
            return

    print(f"🏷️ Updating Android App Name to: {app_name}")
    
    if os.path.exists(STRINGS_XML):
        with open(STRINGS_XML, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace the app_name string resource
        new_content = re.sub(
            r'(<string name="app_name">)(.*?)(</string>)',
            rf'\1{app_name}\3',
            content
        )
        
        with open(STRINGS_XML, "w", encoding="utf-8") as f:
            f.write(new_content)

def generate_random_password(length=16):
    """Generate a cryptographically secure password for keystore signing."""
    # 🔒 P0 Security: Use secrets module (CSPRNG) instead of random (Mersenne Twister)
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return ''.join(secrets.choice(chars) for _ in range(length))

def find_keytool():
    """Attempt to find keytool in common locations."""
    # Check if it's in PATH
    try:
        subprocess.run(["keytool", "-help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return "keytool"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check common Android Studio locations on Windows
    win_path = r"C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
    if os.path.exists(win_path):
        return f'"{win_path}"'
        
    # Check Mac
    mac_path = "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/keytool"
    if os.path.exists(mac_path):
        return f'"{mac_path}"'

    print("❌ Could not find 'keytool'. Please ensure Java/JDK is installed and in your PATH.")
    sys.exit(1)

def setup_keystore(password):
    """Generate the keystore and properties file if they don't exist."""
    if not os.path.exists(KEYSTORE_FILE):
        print("\n🔑 Generating new release keystore...")
        keytool = find_keytool()
        
        cmd = f'{keytool} -genkey -v -keystore "{KEYSTORE_FILE}" -alias pywebapp -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=PyWebApp, OU=Dev, O=Org, L=City, ST=State, C=US" -storepass "{password}" -keypass "{password}"'
        
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            print("❌ Failed to generate keystore.")
            sys.exit(result.returncode)
        print(f"✅ Keystore created at {KEYSTORE_FILE}")
    else:
        print(f"\n✅ Keystore already exists at {KEYSTORE_FILE}")

    if not os.path.exists(PROPERTIES_FILE):
        print("📝 Creating keystore.properties...")
        with open(PROPERTIES_FILE, "w") as f:
            f.write(f"storeFile=pywebapp-release.keystore\n")
            f.write(f"storePassword={password}\n")
            f.write(f"keyAlias=pywebapp\n")
            f.write(f"keyPassword={password}\n")
        print(f"✅ Created {PROPERTIES_FILE}")
    else:
        print(f"✅ {PROPERTIES_FILE} already exists.")

def build_apk(clean=False):
    """Run Gradle to build the release APK."""
    print("\n📦 Building Signed Release APK via Gradle...")
    if clean:
        print("🧼 Performing clean build...")
    
    is_windows = sys.platform.startswith('win')
    gradlew = "gradlew.bat" if is_windows else "./gradlew"
    gradle_path = os.path.join(ANDROID_DIR, gradlew)

    if not os.path.exists(gradle_path):
        print("\n❌ Build failed: Gradle Wrapper not found!")
        sys.exit(1)
    
    tasks = ["assembleRelease"]
    if clean:
        tasks.insert(0, "clean")
        
    result = subprocess.run([gradle_path] + tasks, cwd=ANDROID_DIR)
    if result.returncode != 0:
        print("\n❌ APK Build failed.")
        sys.exit(result.returncode)
        
def main():
    parser = argparse.ArgumentParser(description="Build signed Android APK")
    parser.add_argument("--password", help="Password for keystore generation")
    parser.add_argument("--clean", action="store_true", help="Perform clean build")
    parser.add_argument("--install", action="store_true", help="Install APK after build")
    args = parser.parse_args()

    # Step 1: Ensure frontend & backend are synced
    print("🔄 Syncing Python & Frontend files...")
    from pywebapp.scripts.build_android import main as sync_main, install_apk as smart_install
    # We pass --sync-only to the debug script to just handle files
    import sys as pysys
    old_argv = pysys.argv
    pysys.argv = [pysys.argv[0], "--sync-only", "--skip-frontend"]
    sync_main()
    pysys.argv = old_argv

    # Step 1.5: Update Branding (Name & Icon)
    update_android_branding()

    # Step 2 & 3: Keystore setup
    password = args.password or generate_random_password()
    setup_keystore(password)

    # Step 4: Gradle Build
    apk_path = build_apk(clean=args.clean)
    
    # Step 5: Smart Install
    if args.install:
        smart_install()

if __name__ == "__main__":
    main()
