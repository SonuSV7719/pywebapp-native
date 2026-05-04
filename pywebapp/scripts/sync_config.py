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
    
    print(f"🔄 Syncing config for Web: {app_name}")
    with open(ENV_PATH, "w") as f:
        f.write(f"VITE_APP_NAME={app_name}\n")

if __name__ == "__main__":
    sync_config()
