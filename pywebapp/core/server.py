"""
PyWebApp Internal HTTP Server (Flask-Powered).

A production-grade HTTP server that serves the React frontend and exposes
a REST API for Python IPC — enabling Desktop, Web, and future platforms
to communicate with Python using the same codebase.

Endpoints:
    GET  /                → serves index.html (with API marker injected)
    GET  /assets/*        → serves static files (JS, CSS, images, fonts)
    POST /api/dispatch    → routes to core.api.dispatch()
    GET  /api/schema      → returns all registered methods + parameter info
    GET  /api/health      → returns server status
    GET  /*               → SPA fallback (returns index.html for React Router)

Usage:
    from pywebapp.core.server import start_server, start_server_blocking

    # Background (for Desktop — returns immediately)
    server_thread, port = start_server("./frontend/dist", port=0)

    # Blocking (for CLI `pywebapp serve` — blocks until Ctrl+C)
    start_server_blocking("./frontend/dist", port=18090)
"""

import json
import os
import socket
import sys
import threading
import atexit
from typing import Tuple, Optional

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# Lazy import to avoid circular dependency at module level
_dispatch = None
_get_schema = None
_list_methods = None


def _find_project_root():
    """Search upwards for pywebapp.json to find the project anchor."""
    curr = os.getcwd()
    while curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "pywebapp.json")):
            return curr
        curr = os.path.dirname(curr)
    return os.getcwd()

def _auto_load_handlers():
    """
    Discover and import all user handlers.
    Delegates to the centralized discovery engine.
    """
    from pywebapp.core.discovery import discover_handlers
    discover_handlers()


def _ensure_api_loaded():
    """Lazily import the dispatch functions and auto-load handlers."""
    global _dispatch, _get_schema, _list_methods
    if _dispatch is None:
        # First, load all user code
        _auto_load_handlers()
        
        # Then, import the dispatcher
        from pywebapp.core.api import dispatch, get_schema, list_methods
        _dispatch = dispatch
        _get_schema = get_schema
        _list_methods = list_methods


def _get_version() -> str:
    """Get the PyWebApp version string."""
    try:
        from pywebapp import __version__
        return __version__
    except Exception:
        return "unknown"


# ─── Flask App Factory ────────────────────────────────────────────────────────

def create_app(static_dir: str) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        static_dir: Absolute path to the frontend/dist directory.

    Returns:
        Configured Flask app instance.
    """
    static_dir = os.path.abspath(static_dir)

    app = Flask(
        __name__,
        static_folder=static_dir,
        static_url_path="",
    )

    # Disable verbose Flask logs in production
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    # 🔒 Security: Dynamic CORS configuration
    # Default to secure local-only, but allow overrides for web deployments
    allowed_origins = [
        "http://localhost:*",
        "http://127.0.0.1:*",
        "http://[::1]:*",
    ]
    
    # Try to load custom CORS from pywebapp.json
    try:
        project_root = _find_project_root()
        config_path = os.path.join(project_root, "pywebapp.json")
        if os.path.exists(config_path):
            import json
            with open(config_path, "r") as f:
                config = json.load(f)
                if "cors_origins" in config:
                    allowed_origins = config["cors_origins"]
    except Exception:
        pass

    CORS(app, origins=allowed_origins)

    # ── API Routes ────────────────────────────────────────────────────────

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "server": "PyWebApp Server",
            "version": _get_version(),
        })

    @app.route("/api/schema", methods=["GET"])
    def schema():
        """Return full schema of all registered Python methods."""
        _ensure_api_loaded()
        return jsonify(_get_schema())

    @app.route("/api/methods", methods=["GET"])
    def methods():
        """Return list of all registered method names and descriptions."""
        _ensure_api_loaded()
        return jsonify(_list_methods())

    @app.route("/api/dispatch", methods=["POST"])
    def dispatch():
        """
        Main IPC endpoint.
        Body: { "method": "add", "params": [5, 7] }
        Response: { "success": true, "result": 12, "method": "add" }
        """
        _ensure_api_loaded()

        # Parse request body
        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False,
                "error": "Empty or invalid JSON body. Expected: {\"method\": \"...\", \"params\": [...]}",
            }), 400

        method = body.get("method")
        params = body.get("params", [])

        if not method:
            return jsonify({
                "success": False,
                "error": "Missing 'method' field in request body.",
            }), 400

        # Dispatch to the registered Python handler
        result = _dispatch(method, params)
        return jsonify(result)

    # ── Static File Serving + SPA Fallback ────────────────────────────────

    @app.route("/", methods=["GET"])
    def serve_index():
        """Serve index.html with the API marker injected."""
        return _serve_html_with_marker(static_dir)

    @app.errorhandler(404)
    def spa_fallback(e):
        """
        SPA Fallback: If no file matches, return index.html.
        This enables React Router (client-side routing) to work correctly.
        """
        # Check if the request is for an actual file (has an extension)
        if "." in request.path.split("/")[-1]:
            return jsonify({"error": "File not found", "path": request.path}), 404

        # For all other paths, serve index.html (React Router will handle it)
        return _serve_html_with_marker(static_dir)

    return app


def _serve_html_with_marker(static_dir: str):
    """
    Serve index.html with the __PYWEBAPP_API_URL__ marker injected.
    This tells the bridge to use fetch() instead of mock mode.
    """
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.isfile(index_path):
        return "index.html not found", 404

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Inject the API marker so the bridge auto-detects 'web' mode
    marker = '<script>window.__PYWEBAPP_API_URL__="/api/dispatch";</script>'
    if marker not in html:
        html = html.replace("<head>", f"<head>\n    {marker}", 1)

    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ─── Server Launchers ─────────────────────────────────────────────────────────

def find_free_port() -> int:
    """Find a free port on localhost using OS auto-assignment."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def start_server(
    static_dir: str,
    port: int = 0,
    host: str = "127.0.0.1",
) -> Tuple[threading.Thread, int]:
    """
    Start the PyWebApp server in a background daemon thread.

    Used by the Desktop runner — starts the server, returns the port,
    then the caller opens pywebview pointing to http://localhost:{port}.

    Args:
        static_dir: Path to the frontend/dist directory.
        port: Port to bind to. Use 0 for auto-assignment.
        host: Host to bind to. Default is localhost only.

    Returns:
        Tuple of (server_thread, actual_port).
    """
    if port == 0:
        port = find_free_port()

    app = create_app(static_dir)

    thread = threading.Thread(
        target=app.run,
        kwargs={"host": host, "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    thread.start()

    return thread, port


def start_server_blocking(
    static_dir: Optional[str] = None,
    port: int = 18090,
    host: str = "127.0.0.1",
):
    """
    Start the PyWebApp server in the foreground (blocking).
    """
    # Validate static dir if provided
    if static_dir:
        index_html = os.path.join(static_dir, "index.html")
        if not os.path.isfile(index_html):
            print(f"⚠️  Warning: Frontend build not found at: {static_dir}")
            print("   Static file serving will be disabled. API remains active.")
    else:
        print("💡 API-Only Mode: No static directory provided.")

    # Eagerly load handlers
    _ensure_api_loaded()
    methods = _list_methods()

    print(f"\n🚀 PyWebApp API Server running at http://{host}:{port}")
    print(f"📡 API endpoint: http://{host}:{port}/api/dispatch")
    print(f"💊 Health check: http://{host}:{port}/api/health")
    print(f"📋 Registered methods: {', '.join(methods.keys()) if methods else '(none)'}")
    print(f"\n   Press Ctrl+C to stop.\n")

    app = create_app(static_dir or os.getcwd())

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
