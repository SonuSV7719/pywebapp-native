"""
PyWebApp Desktop Builder
Compiles the project into a standalone executable.
Usage: python -m pywebapp.scripts.build_desktop
"""
import os
import subprocess
import shutil
import sys

def get_project_root():
    """Search upwards for pywebapp.json to find the project anchor."""
    current = os.getcwd()
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "pywebapp.json")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()

def build_desktop():
    PROJECT_ROOT = get_project_root()
    FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
    DIST_DIR = os.path.join(FRONTEND_DIR, 'dist')
    
    print("🚀 Starting Desktop Build Pipeline...")

    # 1. Build Frontend (using cwd instead of os.chdir)
    print("📦 Building Frontend...")
    subprocess.run(['npm', 'install'], check=True, shell=True, cwd=FRONTEND_DIR)
    subprocess.run(['npm', 'run', 'build'], check=True, shell=True, cwd=FRONTEND_DIR)

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
    
    dist_data = f"{DIST_DIR}{os.pathsep}frontend/dist"
    backend_dir = os.path.join(PROJECT_ROOT, "backend")
    backend_data = f"{backend_dir}{os.pathsep}backend"
    config_data = f"{os.path.join(PROJECT_ROOT, 'pywebapp.json')}{os.pathsep}."
    
    # Find the run_desktop script from the pywebapp package
    run_desktop_path = os.path.join(os.path.dirname(__file__), "run_desktop.py")
    
    pyinstaller_cmd = [
        'pyinstaller',
        '--noconfirm',
        '--onefile',
        '--windowed',
        f'--add-data={dist_data}',
        f'--add-data={backend_data}',
        f'--add-data={config_data}',
        f'--name={app_name}',
        run_desktop_path
    ]

    if app_icon:
        icon_full_path = os.path.join(PROJECT_ROOT, app_icon)
        if os.path.exists(icon_full_path):
            # 🖼️ Windows specific: PyInstaller requires .ico
            if sys.platform == "win32" and not icon_full_path.lower().endswith(".ico"):
                try:
                    from PIL import Image
                    print("  🎨 Converting icon to .ico for Windows...")
                    ico_path = os.path.join(PROJECT_ROOT, "app_icon.ico")
                    with Image.open(icon_full_path) as img:
                        # Standard ICO sizes
                        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                        img.save(ico_path, format='ICO', sizes=sizes)
                    pyinstaller_cmd.append(f'--icon={ico_path}')
                except Exception as e:
                    print(f"  ⚠️  Icon conversion failed: {e}. Using raw file.")
                    pyinstaller_cmd.append(f'--icon={icon_full_path}')
            else:
                pyinstaller_cmd.append(f'--icon={icon_full_path}')

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("\n✅ Desktop Build Successful!")
        print(f"👉 Executable available in: {os.path.join(PROJECT_ROOT, 'dist')}")

        # Cleanup temp ico
        temp_ico = os.path.join(PROJECT_ROOT, "app_icon.ico")
        if os.path.exists(temp_ico):
            os.remove(temp_ico)
    except FileNotFoundError:
        print("\n❌ Error: PyInstaller not found. Please run: pip install pyinstaller pywebview")
    except Exception as e:
        print(f"\n❌ Build failed: {e}")

def main():
    build_desktop()

if __name__ == "__main__":
    main()
