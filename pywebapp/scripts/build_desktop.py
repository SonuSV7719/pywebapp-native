"""
PyWebApp Desktop Builder
Compiles the project into a standalone executable.
Usage: python -m pywebapp.scripts.build_desktop
"""
import os
import subprocess
import shutil
import sys

def build_desktop():
    PROJECT_ROOT = os.getcwd()
    FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
    DIST_DIR = os.path.join(FRONTEND_DIR, 'dist')
    
    print("🚀 Starting Desktop Build Pipeline...")

    # 1. Build Frontend
    print("📦 Building Frontend...")
    os.chdir(FRONTEND_DIR)
    subprocess.run(['npm', 'install'], check=True, shell=True)
    subprocess.run(['npm', 'run', 'build'], check=True, shell=True)

    # 2. Read Configuration
    print("📖 Reading pywebapp.json...")
    import json
    config_path = os.path.join(PROJECT_ROOT, 'pywebapp.json')
    app_name = "PyWebApp"
    app_icon = None
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            app_name = config.get("app_name", "PyWebApp")
            app_icon = config.get("icon_path")

    # 3. Prepare PyInstaller Command
    print(f"📦 Packaging '{app_name}' with PyInstaller...")
    os.chdir(PROJECT_ROOT)
    
    dist_data = f"{DIST_DIR}{os.pathsep}frontend/dist"
    backend_data = f"backend{os.pathsep}backend"
    
    # Find the run_desktop script from the pywebapp package
    run_desktop_path = os.path.join(os.path.dirname(__file__), "run_desktop.py")
    
    pyinstaller_cmd = [
        'pyinstaller',
        '--noconfirm',
        '--onefile',
        '--windowed',
        f'--add-data={dist_data}',
        f'--add-data={backend_data}',
        f'--name={app_name}',
        run_desktop_path
    ]

    if app_icon and os.path.exists(os.path.join(PROJECT_ROOT, app_icon)):
        pyinstaller_cmd.append(f'--icon={app_icon}')

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("\n✅ Desktop Build Successful!")
        print(f"👉 Executable available in: {os.path.join(PROJECT_ROOT, 'dist')}")
    except FileNotFoundError:
        print("\n❌ Error: PyInstaller not found. Please run: pip install pyinstaller pywebview")
    except Exception as e:
        print(f"\n❌ Build failed: {e}")

def main():
    build_desktop()

if __name__ == "__main__":
    main()
