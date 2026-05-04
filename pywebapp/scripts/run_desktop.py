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
        
        # Windows file path to URI fix (Using pathlib for 100% compliance)
        from pathlib import Path
        url = Path(index_html).absolute().as_uri()

    bridge = DesktopBridge()
    
    safe_print("🚀 Launching PyWebApp Desktop...")
    window = webview.create_window(
        'PyWebApp Desktop', 
        url=url,
        js_api=bridge,
        width=1200,
        height=800
    )
    
    # Start the app with the internal HTTP server enabled (Native Universal Fix)
    # This avoids file:// URI issues and provides a consistent local environment
    webview.start(debug=is_dev, http_server=not is_dev)

if __name__ == '__main__':
    main()
