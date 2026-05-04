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

    def ping(self) -> str:
        """
        Health check endpoint.
        Returns a simple acknowledgment.
        """
        return json.dumps({"status": "ok", "message": "Bridge is alive"})
