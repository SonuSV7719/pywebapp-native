"""
Desktop application launcher using pywebview.

Creates a native window with an embedded WebView that loads the React frontend
and exposes Python functions via the BridgeApi js_api.

Features:
    - Production mode: loads built frontend from dist/
    - Dev mode (--dev): loads from Vite dev server with HMR
    - Hot reload (--dev): Python modules auto-reload on file save
    - Debug mode (--debug): opens DevTools panel

Usage:
    python -m pywebapp.desktop.runner           # Production mode
    python -m pywebapp.desktop.runner --debug   # With DevTools
    python -m pywebapp.desktop.runner --dev     # Dev mode (Vite HMR + Python hot reload)
"""

import argparse
import os
import sys

from pywebapp.core.logger import get_logger

logger = get_logger("desktop.main")


def get_project_root():
    """Get the root directory of the project, handling PyInstaller's _MEIPASS."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        return sys._MEIPASS

    # Running from source — the project root is the current working directory
    return os.getcwd()


def get_frontend_url(dev_mode: bool = False) -> str:
    """
    Returns the URL to load in the WebView.

    In dev mode, loads from Vite's dev server (hot-reload).
    In production, loads the built static files.
    """
    if dev_mode:
        return "http://localhost:5173"

    project_root = get_project_root()

    # Look for built frontend
    dist_dir = os.path.join(project_root, "frontend", "dist")
    index_file = os.path.join(dist_dir, "index.html")

    if not os.path.exists(index_file):
        logger.error(f"Frontend build not found at: {dist_dir}")
        logger.error("Run 'cd frontend && npm install && npm run build' first.")
        sys.exit(1)

    return index_file


def start_hot_reload(window, backend_dir: str):
    """
    Start the Python hot reload watcher (dev mode only).
    Watches backend/ for .py file changes and reloads modules in-place.
    """
    try:
        from pywebapp.desktop.hot_reload import HotReloader

        reloader = HotReloader(
            watch_dir=backend_dir,
            window=window,
            on_reload=lambda modules: logger.info(
                f"🔥 Hot reloaded: {', '.join(modules)}"
            ),
        )
        reloader.start()
        return reloader
    except Exception as e:
        logger.warning(f"Hot reload failed to start: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="PyWebApp Desktop Launcher")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (DevTools available)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Load from Vite dev server + enable Python hot reload",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=900,
        help="Window width (default: 900)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=700,
        help="Window height (default: 700)",
    )
    args = parser.parse_args()

    # Import pywebview (deferred to give better error messages)
    try:
        import webview
    except ImportError:
        logger.error("pywebview is not installed.")
        logger.error("Install it with: pip install pywebview")
        sys.exit(1)

    # Import bridge
    from pywebapp.desktop.bridge import BridgeApi

    # Create API instance
    api = BridgeApi()

    # Get frontend URL
    url = get_frontend_url(dev_mode=args.dev)
    logger.info(f"Loading frontend from: {url}")

    # Create window
    window = webview.create_window(
        title="PyWebApp — Cross-Platform IPC Demo",
        url=url,
        js_api=api,
        width=args.width,
        height=args.height,
        resizable=True,
        min_size=(400, 500),
        text_select=False,
    )

    # Setup hot reload callback (runs after window is created)
    reloader = None
    project_root = get_project_root()

    def on_started():
        nonlocal reloader
        if args.dev:
            backend_dir = os.path.join(project_root, "backend")
            reloader = start_hot_reload(window, backend_dir)

    logger.info("Starting pywebview...")
    logger.info(f"Debug mode: {args.debug}")
    logger.info(f"Dev mode: {args.dev}")
    if args.dev:
        logger.info("🔥 Hot reload enabled for backend/ Python files")
        logger.info("📦 Frontend loading from Vite dev server (HMR active)")

    # Start the application
    webview.start(
        func=on_started,
        debug=args.debug or args.dev,  # Always debug in dev mode
        http_server=args.dev,
    )

    # Cleanup
    if reloader:
        reloader.stop()

    logger.info("Application closed.")


if __name__ == "__main__":
    main()
