"""
Desktop bridge — Exposes Python functions to JavaScript via pywebview's js_api.

This class is passed to pywebview's create_window() as the js_api parameter.
All public methods become available in JavaScript as:
    window.pywebview.api.<method_name>(...)
"""

import json
import os
import sys
import threading
from typing import Optional

from pywebapp.core.api import dispatch, dispatch_json, list_methods
from pywebapp.core.logger import get_logger

logger = get_logger("desktop.bridge")


class BridgeApi:
    """
    JavaScript API bridge for pywebview.

    Exposes a single `call(method, params_json)` method to JavaScript,
    which routes to the appropriate Python handler via the API dispatcher.

    All methods return JSON strings for consistency.
    """

    def __init__(self):
        self._lock = threading.Lock()
        logger.info("BridgeApi initialized")

    def call(self, method: str, params_json: str = "[]") -> str:
        """
        Main IPC entry point. Called from JavaScript as:
            const result = await pywebview.api.call('add', '[5, 7]');

        Args:
            method: Name of the Python method to invoke.
            params_json: JSON string of the parameters array.

        Returns:
            JSON string with the result or error.
        """
        logger.info(f"Bridge.call: method='{method}', params={params_json}")

        with self._lock:
            result = dispatch_json(method, params_json)

        logger.debug(f"Bridge.call result: {result[:200]}...")
        return result

    def list_methods(self) -> str:
        """
        Returns a JSON object of all available methods.
        Useful for UI introspection.
        """
        methods = list_methods()
        return json.dumps(methods)

    def pickFile(self, dialog_title: str = "Select File", file_types: list = None) -> str:
        """
        Natively pick a file and return its absolute path.
        """
        if file_types is None:
            file_types = ["All files (*.*)"]
            
        import webview
        window = webview.active_window()
        if not window:
            return json.dumps({"success": False, "error": "No active window"})
            
        try:
            result = window.create_file_dialog(webview.OPEN_DIALOG, dialog_title=dialog_title, file_types=file_types)
            if result and len(result) > 0:
                file_path = result[0]
                # Format response for the JS bridge
                response = {
                    "success": True, 
                    "path": file_path, 
                    "uri": f"file://{file_path}", 
                    "name": os.path.basename(file_path)
                }
                return json.dumps(response)
        except Exception as e:
            logger.error(f"pickFile error: {e}")
            return json.dumps({"success": False, "error": str(e)})
            
        return json.dumps({"success": False, "error": "Cancelled"})

    def ping(self) -> str:
        """
        Health check endpoint.
        Returns a simple acknowledgment.
        """
        return json.dumps({"status": "ok", "message": "Bridge is alive"})
