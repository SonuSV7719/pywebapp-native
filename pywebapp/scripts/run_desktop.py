"""
PyWebApp Desktop Runner
Allows running the same React/Python core as a Native Desktop App.
Requires: pip install pywebview
"""
import os
import sys
import json

# 🛡️ ENCODING SHIELD: Prevent crashes on Windows when printing emojis
# Only run if stdout exists (it might be None in windowed mode)
if sys.platform == "win32" and sys.stdout is not None:
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

def safe_print(msg):
    """Prints only if stdout is available (Prevents EXE crashes)"""
    if sys.stdout is not None:
        try:
            print(msg)
        except Exception:
            pass

# 🏛️ PATH FIX: Ensure we can find the project structure correctly
def get_project_root():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    
    # Search upwards for pywebapp.json starting from CWD
    current = os.getcwd()
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "pywebapp.json")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()

PROJECT_ROOT = get_project_root()

# 🛡️ SAFETY CHECK: Verify we are actually in a PyWebApp project
if not os.path.exists(os.path.join(PROJECT_ROOT, "pywebapp.json")) and not hasattr(sys, '_MEIPASS'):
    safe_print("❌ Error: Could not find 'pywebapp.json'.")
    safe_print("   Please run this command from inside your PyWebApp project folder.")
    sys.exit(1)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from pywebapp.core.api import dispatch
    safe_print("Backend logic connected via pywebapp.core.")
except ImportError as e:
    safe_print(f"Error: Could not load pywebapp.core.api. {e}")
    dispatch = None

import webview

class DesktopBridge:
    def dispatch(self, method, params_json):
        params = json.loads(params_json) if params_json else []
        result = dispatch(method, params)
        return json.dumps(result)

    def showToast(self, message):
        print(f"[TOAST]: {message}")

    def shareText(self, text):
        safe_print(f"[SHARE]: {text}")

    def pickFile(self, title, file_types):
        """Native Desktop File Picker Driver"""
        # pywebview provides a native file dialog
        result = webview.active_window().create_file_dialog(
            webview.OPEN_DIALOG, 
            allow_multiple=False, 
            file_types=file_types
        )
        if result:
            return json.dumps({"success": True, "uri": result[0]})
        return json.dumps({"success": False, "error": "User cancelled"})

    def getBase64FromUri(self, uri):
        """Native Desktop Image Reader Driver"""
        import base64
        try:
            # On Desktop, the URI is just a local file path
            path = uri.replace('file://', '')
            if os.path.exists(path):
                with open(path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    # Detect mime type from extension
                    ext = os.path.splitext(path)[1].lower()
                    mime = "image/jpeg" if ext in ['.jpg', '.jpeg'] else "image/png"
                    return json.dumps({"success": True, "base64": f"data:{mime};base64,{encoded_string}"})
            return json.dumps({"success": False, "error": "File not found"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

def main():
    # Detect if we should use the Dev Server (Hot Reload) or static files
    is_dev = "--dev" in sys.argv
    
    if is_dev:
        url = "http://localhost:5173"
        safe_print(f"🔥 Hot-Reload Mode Active: Connecting to {url}")
    else:
        # Path to the frontend build
        if hasattr(sys, '_MEIPASS'):
            frontend_dist = os.path.join(sys._MEIPASS, 'frontend', 'dist')
        else:
            frontend_dist = os.path.join(PROJECT_ROOT, 'frontend', 'dist')
            
        index_html = os.path.join(frontend_dist, 'index.html')
        if not os.path.exists(index_html):
            safe_print("Error: Frontend build not found.")
            return
        
        # 🚀 Start our own Flask server in a background thread
        # This replaces the broken file:// URI approach and pywebview's unreliable http_server
        from pywebapp.core.server import start_server
        server_thread, port = start_server(frontend_dist, port=0)
        url = f"http://localhost:{port}"
        safe_print(f"📡 Internal server started at {url}")

    # 🏷️ Load Configuration from pywebapp.json (single read)
    config_path = os.path.join(PROJECT_ROOT, "pywebapp.json")
    app_name = "PyWebApp Desktop"
    icon_path = None
    width = 1200
    height = 800
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                
                # Branding
                desktop_config = config.get("desktop", {})
                app_name = desktop_config.get("app_name", config.get("app_name", app_name))
                icon_rel = config.get("icon_path")
                if icon_rel:
                    icon_path = os.path.join(PROJECT_ROOT, icon_rel)
                
                # Window dimensions (desktop block → global → default)
                width = desktop_config.get("window_width", config.get("window_width", width))
                height = desktop_config.get("window_height", config.get("window_height", height))
        except Exception:
            pass

    bridge = DesktopBridge()
    
    safe_print(f"🚀 Launching {app_name} ({width}x{height})...")
    window = webview.create_window(
        app_name, 
        url=url,
        js_api=bridge,
        width=width,
        height=height
    )
    
    # Start the app (no http_server flag needed — we run our own)
    webview.start(debug=is_dev)

if __name__ == '__main__':
    main()
