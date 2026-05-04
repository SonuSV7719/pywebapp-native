"""
PyWebApp CLI Tool
The heart of the PyWebApp framework.
Provides commands for development, building, and deployment.
"""
import os
import sys
import subprocess
import argparse
import shutil
import stat

def remove_readonly(func, path, _):
    "Clear the readonly bit and reattempt the file removal"
    os.chmod(path, stat.S_IWRITE)
    func(path)

def run_command(cmd, cwd=None, shell=True):
    print(f"🛠️ Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.run(cmd, cwd=cwd, shell=shell, check=True)

def build_frontend():
    print("\n📦 Building Frontend...")
    sync_app_config()
    frontend_dir = os.path.join(os.getcwd(), 'frontend')
    run_command("npm install", cwd=frontend_dir)
    run_command("npm run build", cwd=frontend_dir)

def init_project(name):
    print(f"\n🌟 Creating new PyWebApp project: {name}...")
    repo_url = "https://github.com/SonuSV7719/PyWebApp-Framework.git"
    try:
        subprocess.run(["git", "clone", repo_url, name], check=True)
        
        # Cleanup unnecessary folders and files
        project_path = os.path.join(os.getcwd(), name)
        folders_to_remove = ['docs', 'tests', 'packages', '.github', 'build', 'dist']
        files_to_remove = ['pyproject.toml', 'PyWebApp.spec', 'PyWebApp Native.spec', 'LICENSE', 'requirements.txt', 'master_build.py']
        
        for folder in folders_to_remove:
            path = os.path.join(project_path, folder)
            if os.path.exists(path):
                shutil.rmtree(path, onerror=remove_readonly)
                print(f"🧹 Removed folder: {folder}/")

        for file in files_to_remove:
            path = os.path.join(project_path, file)
            if os.path.exists(path):
                os.remove(path)
                print(f"🧹 Removed file: {file}")

        # Remove egg-info if they exist
        for item in os.listdir(project_path):
            if item.endswith('.egg-info'):
                shutil.rmtree(os.path.join(project_path, item), onerror=remove_readonly)
                print(f"🧹 Removed {item}/")

        # Remove framework-only files from backend (keep only handlers.py)
        backend_path = os.path.join(project_path, "backend")
        framework_files = ['api.py', 'registry.py', 'context.py', 'logger.py']
        for f in framework_files:
            fpath = os.path.join(backend_path, f)
            if os.path.exists(fpath):
                os.remove(fpath)
                print(f"🧹 Removed backend/{f} (now in pip package)")

        # Remove desktop/ and scripts/ folders (now in pip package)
        for folder in ['desktop', 'scripts']:
            path = os.path.join(project_path, folder)
            if os.path.exists(path):
                shutil.rmtree(path, onerror=remove_readonly)
                print(f"🧹 Removed {folder}/ (now in pip package)")

        # Remove frontend/src/bridge.js (now in npm package)
        bridge_path = os.path.join(project_path, "frontend", "src", "bridge.js")
        if os.path.exists(bridge_path):
            os.remove(bridge_path)
            print("🧹 Removed frontend/src/bridge.js (now in npm package)")

        # Install npm dependencies (including pywebapp-bridge)
        frontend_path = os.path.join(project_path, "frontend")
        if os.path.exists(frontend_path):
            print("\n📦 Installing frontend dependencies...")
            try:
                subprocess.run(["npm", "install"], cwd=frontend_path, shell=True, check=True)
                print("✅ Frontend dependencies installed")
            except Exception as e:
                print(f"⚠️  npm install failed: {e}. Run 'cd {name}/frontend && npm install' manually.")

        # Fresh start: Re-initialize Git to remove framework history
        git_path = os.path.join(project_path, ".git")
        if os.path.exists(git_path):
            shutil.rmtree(git_path, onerror=remove_readonly)
            subprocess.run(["git", "init"], cwd=project_path, check=True)
            print("✨ Git re-initialized for a fresh start.")

        print(f"\n✅ Project '{name}' created successfully!")
        print(f"👉 To start: cd {name} && pywebapp dev")
    except Exception as e:
        print(f"❌ Failed to create project: {e}")

def sync_app_config():
    try:
        from pywebapp.scripts.sync_config import sync_config
        sync_config()
    except Exception as e:
        print(f"⚠️ Warning: Could not sync pywebapp.json config: {e}")

def dev_server():
    print("\n🚀 Launching Development Environment...")
    sync_app_config()
    
    frontend_dir = os.path.join(os.getcwd(), 'frontend')
    # Start Vite in background (provides Hot Module Replacement)
    subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir, shell=True)
    
    # Give Vite a second to start
    import time
    time.sleep(2)
    
    # Launch the Desktop window in Dev Mode using the package's runner
    from pywebapp.scripts.run_desktop import main as run_desktop_main
    sys.argv = [sys.argv[0], "--dev"]
    run_desktop_main()

def main():
    parser = argparse.ArgumentParser(description="PyWebApp Framework CLI")
    parser.add_argument('command', choices=['init', 'dev', 'build-android', 'build-desktop', 'build-linux', 'build-web'], 
                        help='Command to execute')
    parser.add_argument('name', nargs='?', help='Project name for init command')
    
    args = parser.parse_args()

    try:
        if args.command == 'init':
            if not args.name:
                print("❌ Error: Please provide a project name. Usage: pywebapp init <name>")
                return
            init_project(args.name)
        elif args.command == 'dev':
            dev_server()
        elif args.command == 'build-web':
            build_frontend()
            print("\n🌐 Web build complete! Folder: frontend/dist")
        elif args.command == 'build-android':
            build_frontend()
            from pywebapp.scripts.build_android_release import main as release_main
            release_main()
        elif args.command == 'build-desktop' or args.command == 'build-linux':
            build_frontend()
            from pywebapp.scripts.build_desktop import main as desktop_main
            desktop_main()
        
        print(f"\n✨ {args.command.capitalize()} completed successfully!")
    except Exception as e:
        print(f"\n❌ Command failed: {e}")

if __name__ == "__main__":
    main()
