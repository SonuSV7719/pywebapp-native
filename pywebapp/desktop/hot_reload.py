"""
Hot Reload System for PyWebApp Desktop.

Watches the backend/ directory for Python file changes and reloads
modules in-place using importlib.reload(). This gives instant feedback
when editing handler functions — no app restart required.

Architecture:
    watchdog FileSystemObserver
        → detects .py change in backend/
        → debounce (300ms)
        → importlib.reload() on changed modules
        → re-import handlers to refresh @register decorators
        → notify WebView via JS event (optional toast)

Usage:
    # Automatically started when desktop app runs with --dev flag
    from pywebapp.desktop.hot_reload import HotReloader
    reloader = HotReloader(backend_dir, window=webview_window)
    reloader.start()

IMPORTANT: Development only. Never include in production builds.
"""

import importlib
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional

from pywebapp.core.logger import get_logger

logger = get_logger("hot_reload")

# Debounce interval in seconds
DEBOUNCE_SECONDS = 0.3


class HotReloader:
    """
    Watches backend Python files and reloads modules on change.

    This enables true hot reload for the Python backend — edit a handler
    function and see the result immediately in the running app.

    The reload process:
        1. Detect file change via watchdog
        2. Debounce to avoid multi-trigger
        3. Reload the specific module via importlib.reload()
        4. Re-import handlers to refresh @register decorators
        5. Optionally notify the WebView (toast notification)
    """

    def __init__(
        self,
        watch_dir: str,
        window=None,
        on_reload=None,
    ):
        """
        Args:
            watch_dir: Directory to watch for changes (typically backend/).
            window: pywebview window instance (for JS notifications).
            on_reload: Optional callback function called after successful reload.
        """
        self.watch_dir = os.path.abspath(watch_dir)
        self.window = window
        self.on_reload = on_reload
        self._observer = None
        self._debounce_timer = None
        self._lock = threading.Lock()
        self._pending_files = set()
        self._running = False

        logger.info(f"HotReloader initialized: watching {self.watch_dir}")

    def start(self):
        """Start watching for file changes."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.error(
                "watchdog is not installed. Hot reload disabled.\n"
                "Install with: pip install watchdog"
            )
            return

        reloader = self  # capture reference for inner class

        class ChangeHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('.py'):
                    reloader._on_file_changed(event.src_path)

            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith('.py'):
                    reloader._on_file_changed(event.src_path)

        self._observer = Observer()
        self._observer.schedule(
            ChangeHandler(),
            self.watch_dir,
            recursive=True,
        )
        self._observer.daemon = True
        self._observer.start()
        self._running = True

        logger.info(f"🔥 Hot reload active — watching: {self.watch_dir}")

    def stop(self):
        """Stop watching for file changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._running = False
            logger.info("Hot reload stopped")

    def _on_file_changed(self, filepath: str):
        """Called when a .py file changes. Debounces before reloading."""
        with self._lock:
            self._pending_files.add(filepath)

            # Cancel existing debounce timer
            if self._debounce_timer:
                self._debounce_timer.cancel()

            # Set new debounce timer
            self._debounce_timer = threading.Timer(
                DEBOUNCE_SECONDS,
                self._execute_reload,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _execute_reload(self):
        """Reload all pending changed modules."""
        with self._lock:
            files_to_reload = self._pending_files.copy()
            self._pending_files.clear()

        if not files_to_reload:
            return

        logger.info(f"♻️  Reloading {len(files_to_reload)} module(s)...")

        reloaded_modules = []
        for filepath in files_to_reload:
            module_name = self._filepath_to_module(filepath)
            if module_name and module_name in sys.modules:
                try:
                    module = sys.modules[module_name]
                    importlib.reload(module)
                    reloaded_modules.append(module_name)
                    logger.info(f"  ✅ Reloaded: {module_name}")
                except Exception as e:
                    logger.error(f"  ❌ Failed to reload {module_name}: {e}")

        # After reloading individual modules, re-import handlers
        # to refresh @register decorators in the registry
        if reloaded_modules:
            self._refresh_registry()

        # Notify the WebView
        if reloaded_modules and self.window:
            self._notify_webview(reloaded_modules)

        # Call user callback
        if reloaded_modules and self.on_reload:
            try:
                self.on_reload(reloaded_modules)
            except Exception as e:
                logger.error(f"on_reload callback error: {e}")

        if reloaded_modules:
            logger.info(f"♻️  Reload complete: {reloaded_modules}")

    def _refresh_registry(self):
        """
        Re-import the handlers module to refresh @register decorators.
        This ensures the MethodRegistry has the latest function references.
        """
        try:
            # Reload registry first (in case it changed)
            import pywebapp.core.registry
            importlib.reload(pywebapp.core.registry)

            # Reload user handlers (re-executes @register decorators)
            for module_name in ["backend.handlers", "handlers"]:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])

            # Reload api (re-imports handlers)
            import pywebapp.core.api
            importlib.reload(pywebapp.core.api)

            logger.info("  ✅ Registry refreshed with updated handlers")
        except Exception as e:
            logger.error(f"  ❌ Registry refresh failed: {e}")

    def _filepath_to_module(self, filepath: str) -> Optional[str]:
        """Convert a file path to a Python module name."""
        filepath = os.path.abspath(filepath)

        # Check if it's in the watched directory (user's backend/)
        if filepath.startswith(self.watch_dir):
            project_root = os.path.dirname(self.watch_dir)
            relative = os.path.relpath(filepath, project_root)
            # Convert path to module: backend/handlers.py → backend.handlers
            module_name = relative.replace(os.sep, '.').replace('.py', '')
            return module_name

        return None

    def _notify_webview(self, modules: list):
        """Send a reload notification to the WebView."""
        try:
            module_list = ', '.join(m.split('.')[-1] for m in modules)
            js_code = f"""
                if (window.__onPythonReload) {{
                    window.__onPythonReload('{module_list}');
                }}
            """
            self.window.evaluate_js(js_code)
        except Exception as e:
            logger.debug(f"WebView notification skipped: {e}")

    @property
    def is_running(self) -> bool:
        return self._running
