import json
import os

def sync_config():
    PROJECT_ROOT = os.getcwd()
    CONFIG_PATH = os.path.join(PROJECT_ROOT, "pywebapp.json")
    ENV_PATH = os.path.join(PROJECT_ROOT, "frontend", ".env")
    
    if not os.path.exists(CONFIG_PATH):
        return

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        
    app_name = config.get("app_name", "PyWebApp Native")
    app_version = config.get("version", "1.0.0")
    
    print(f"🔄 Syncing config and branding: {app_name} (v{app_version})")
    with open(ENV_PATH, "w") as f:
        f.write(f"VITE_APP_NAME={app_name}\n")
        f.write(f"VITE_APP_VERSION={app_version}\n")

    # 🖼️ Sync Icons and Titles for Web & Desktop Dev Window
    try:
        from pywebapp.scripts.build_frontend import _sync_web_icon
        _sync_web_icon()
    except Exception as e:
        print(f"⚠️ Warning: Could not sync branding: {e}")

if __name__ == "__main__":
    sync_config()
