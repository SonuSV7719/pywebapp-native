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

def _ensure_vite_android_compat(frontend_dir):
    """
    Auto-patch vite.config.js to ensure Android emulators/devices can connect.
    Vite v6+ has strict host checking that silently drops connections from 
    unknown origins (like 10.0.2.2 or ADB reverse tunnels).
    
    This function ensures:
      - server.host = true  (bind to 0.0.0.0, not just localhost)
      - server.allowedHosts = 'all'  (accept connections from any origin)
    """
    vite_config_path = os.path.join(frontend_dir, "vite.config.js")
    if not os.path.exists(vite_config_path):
        return
    
    with open(vite_config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    modified = False
    
    # Check if host: true is missing from the server block
    if "host:" not in content and "server:" in content:
        content = content.replace(
            "open: false,",
            "open: false,\n    host: true,\n    allowedHosts: 'all',"
        )
        modified = True
    elif "host:" not in content:
        # No server block at all — shouldn't happen with our template but handle it
        content = content.replace(
            "});",
            "  server: {\n    host: true,\n    allowedHosts: 'all',\n  },\n});"
        )
        modified = True
    
    # Check if allowedHosts is missing but host is present
    if "allowedHosts" not in content and "host:" in content:
        content = content.replace(
            "host: true,",
            "host: true,\n    allowedHosts: 'all',"
        )
        modified = True
    
    if modified:
        with open(vite_config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  🛡️ Auto-patched vite.config.js for Android compatibility")
    else:
        print("  ✅ vite.config.js already Android-compatible")

def dev_server(mode="desktop", port=5173):
    sync_app_config()
    frontend_dir = os.path.join(os.getcwd(), 'frontend')

    # 🛡️ Validate project root — prevent WinError 267 crashes
    if not os.path.isdir(frontend_dir):
        print(f"\n❌ Error: No 'frontend/' directory found in {os.getcwd()}")
        print("   Make sure you run 'pywebapp dev' from your project root directory.")
        print("   Example: cd C:\\My_Project\\YourApp && pywebapp dev")
        return

    if mode == "android":
        print("\n🤖 Preparing Android Dev Environment...")
        
        # 0. 🛡️ AUTO-PATCH: Ensure vite.config.js has host:true and allowedHosts:'all'
        #    This is critical for Android emulators/devices to reach the Vite server.
        _ensure_vite_android_compat(frontend_dir)
        
        # 1. 🚀 Start Vite dev server in background FIRST (so emulator can connect)
        print("  ⚡ Starting Vite frontend server on port %d..." % port)
        vite_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port)],
            cwd=frontend_dir, shell=True
        )
        
        import time
        time.sleep(3)  # Give Vite time to start before the emulator tries to connect
        print("  ✅ Vite dev server running on port %d" % port)
        
        try:
            # 2. 🧼 Build and install debug APK
            print("  🔨 Building fresh Debug APK (Clean)...")
            from pywebapp.scripts.build_android import main as build_main
            original_argv = sys.argv.copy()
            sys.argv = [original_argv[0], "--clean", "--install"]
            build_main()
            
            # 3. 🔄 Start the live Python sync engine (blocks until Ctrl+C)
            print("\n🚀 Launching Android Dev Sync (Hot Reload)...")
            from pywebapp.scripts.dev_sync import main as dev_sync_main
            sys.argv = [original_argv[0], "--port", str(port), "--setup-reverse"]
            dev_sync_main()
        except KeyboardInterrupt:
            print("\n👋 Stopping Android dev environment...")
        finally:
            print("🧹 Cleaning up background processes...")
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(vite_proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                vite_proc.terminate()
            print("✅ Cleanup complete.")
        return

    if mode == "web":
        print(f"\n🌐 Launching Web Dev Environment (Port {port})...")
        # 🔗 Pass the backend port to Vite via environment variable
        env = os.environ.copy()
        env["PYWEBAPP_API_PORT"] = "18090" # This matches the backend
        
        vite_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port)], 
            cwd=frontend_dir, 
            shell=True,
            env=env
        )
        
        try:
            # Start Python API server for backend
            print("🐍 Starting Python API server...")
            if os.getcwd() not in sys.path:
                sys.path.insert(0, os.getcwd())
            from pywebapp.core.server import start_server_blocking
            # In web dev mode, we only need the API (Vite handles static files)
            start_server_blocking(port=18090) 
        except KeyboardInterrupt:
            print("\n👋 Stopping web dev server...")
        finally:
            print("🧹 Cleaning up background processes...")
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(vite_proc.pid)], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                vite_proc.terminate()
        return

    # Default: Desktop Mode
    print("\n🚀 Launching Desktop Development Environment...")
    # Start Vite in background (provides Hot Module Replacement)
    vite_proc = subprocess.Popen(["npm", "run", "dev", "--", "--port", str(port)], cwd=frontend_dir, shell=True)
    
    import time
    time.sleep(2)
    
    try:
        from pywebapp.scripts.run_desktop import main as run_desktop_main
        sys.argv = [sys.argv[0], "--dev"]
        run_desktop_main()
    except KeyboardInterrupt:
        print("\n👋 Stopping development server...")
    finally:
        print("🧹 Cleaning up background processes...")
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(vite_proc.pid)], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            vite_proc.terminate()
        print("✅ Cleanup complete.")

def main():
    from pywebapp import __version__
    parser = argparse.ArgumentParser(description="PyWebApp Framework CLI")
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('command', nargs='?', choices=['init', 'dev', 'build-android', 'build-desktop', 'build-linux', 'build-web', 'serve'], 
                        help='Command to execute')
    parser.add_argument('name', nargs='?', help='Project name for init command')
    parser.add_argument('--password', help='Keystore password for build-android')
    parser.add_argument('--port', type=int, default=5173, help='Port for dev/serve command (default: 5173)')
    parser.add_argument('--android', action='store_true', help='Run in Android dev mode')
    parser.add_argument('--desktop', action='store_true', help='Run in Desktop dev mode')
    parser.add_argument('--web', action='store_true', help='Run in Web dev mode')
    parser.add_argument('--clean', action='store_true', help='Perform clean build (Android)')
    parser.add_argument('--install', action='store_true', help='Install APK to device after build (Android)')
    parser.add_argument('--debug', action='store_true', help='Build debug APK instead of release (Android)')
    
    args = parser.parse_args()

    try:
        if not args.command:
            parser.print_help()
            return

        if args.command == 'init':
            if not args.name:
                print("❌ Error: Please provide a project name. Usage: pywebapp init <name>")
                return
            init_project(args.name)
        elif args.command == 'dev':
            mode = None
            if args.android: mode = "android"
            elif args.desktop: mode = "desktop"
            elif args.web: mode = "web"
            
            if mode is None:
                print("\n📱 PyWebApp Dev Menu")
                print("-" * 25)
                print("  [a] Android (Hot Reload)")
                print("  [d] Desktop (Windows/Linux Window)")
                print("  [w] Web (Browser Only)")
                print("  [q] Quit")
                
                choice = input("\n👉 Select mode: ").lower().strip()
                if choice == 'a': mode = "android"
                elif choice == 'd': mode = "desktop"
                elif choice == 'w': mode = "web"
                elif choice == 'q': return
                else:
                    print("⚠️ Invalid choice. Defaulting to Desktop...")
                    mode = "desktop"
            
            dev_server(mode=mode, port=args.port)
        elif args.command == 'build-web':
            build_frontend()
            print("\n🌐 Web build complete! Folder: frontend/dist")
            print("   Run 'pywebapp serve' to test with live Python API.")
        elif args.command == 'serve':
            frontend_dist = os.path.join(os.getcwd(), 'frontend', 'dist')
            if os.getcwd() not in sys.path:
                sys.path.insert(0, os.getcwd())
            from pywebapp.core.server import start_server_blocking
            start_server_blocking(frontend_dist, port=args.port)
        elif args.command == 'build-android':
            build_frontend()
            
            if args.debug:
                # Force Debug Build
                from pywebapp.scripts.build_android import main as debug_main
                sys.argv = [sys.argv[0]]
                if args.clean: sys.argv.append("--clean")
                if args.install: sys.argv.append("--install")
                debug_main()
            else:
                # Default to Release Build
                from pywebapp.scripts.build_android_release import main as release_main
                sys.argv = [sys.argv[0]]
                if args.clean: sys.argv.append("--clean")
                if args.install: sys.argv.append("--install")
                if args.password:
                    sys.argv.extend(["--password", args.password])
                release_main()
        elif args.command == 'build-desktop' or args.command == 'build-linux':
            build_frontend()
            from pywebapp.scripts.build_desktop import main as desktop_main
            sys.argv = [sys.argv[0]]
            desktop_main()
        
        print(f"\n✨ {args.command.capitalize()} completed successfully!")
    except Exception as e:
        print(f"\n❌ Command failed: {e}")

if __name__ == "__main__":
    main()
