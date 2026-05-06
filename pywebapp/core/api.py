"""
IPC API Dispatcher.
Routes method calls from the native bridge to the appropriate handler function.
This is the single entry point for all IPC communication.

Architecture:
    The dispatcher uses the MethodRegistry singleton. Any function decorated with
    @register in the user's handlers.py (or any module) is automatically available
    for IPC calls.

    To add a new method, you ONLY need to add @register() to your function.
    No changes needed in this file, the bridge, or any native code.

Usage:
    result = dispatch("add", [5, 7])
    # Returns: {"success": True, "result": 12, "method": "add"}
"""

import json
import importlib
import traceback
import pkgutil
from typing import Any, Dict, List, Optional

from pywebapp.core import context
from pywebapp.core.logger import get_logger
from pywebapp.core.registry import method_registry

logger = get_logger("api")

# Track whether user handlers have been discovered
_handlers_loaded = False


def _discover_user_handlers():
    """
    Discover and import all user handlers.
    Delegates to the centralized discovery engine.
    """
    global _handlers_loaded
    if _handlers_loaded:
        return

    from pywebapp.core.discovery import discover_handlers
    discover_handlers()
    _handlers_loaded = True


def set_context(data_json: str) -> None:
    """
    Set the global context for Python handlers.
    Expected to be called from the native bridge during initialization.
    """
    try:
        data = json.loads(data_json)
        context.set_context(data)
        logger.info(f"Context updated: {list(data.keys())}")
    except Exception as e:
        logger.error(f"Failed to set context: {e}")


def get_context() -> Dict[str, Any]:
    """Retrieve the global context (delegated)."""
    return context.get_context()


def hide_splash():
    """
    Signal the native side to hide the splash screen.
    This is useful if you want to wait for backend initialization 
    before showing the UI.
    """
    # We use a special internal method name that the bridge listens for
    # or we can use the registry to store a "dismiss" signal.
    from pywebapp.core.registry import method_registry
    if "internal_hide_splash" in method_registry:
        method_registry["internal_hide_splash"]()
    else:
        # Fallback: if not registered, we just log it
        get_logger("api").info("🌊 Splash dismiss requested from Python")
        # In a real bridge, we'd trigger a native call here.
        # For now, we'll ensure the bridge registers this callback.


def dispatch(method: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
    """
    Dispatch an IPC call to the appropriate handler.
    """
    # Ensure user handlers are discovered (fast path guard)
    if not _handlers_loaded:
        _discover_user_handlers()

    if params is None:
        params = []

    logger.info(f"dispatch: method='{method}', params={params}")

    # Check if method exists in registry
    if not method_registry.has_method(method):
        available = list(method_registry.list_methods().keys())
        error_msg = f"Unknown method: '{method}'. Available methods: {available}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "method": method,
        }

    # Execute via registry (which handles middleware)
    try:
        result = method_registry.call(method, params)

        logger.info(f"dispatch: method='{method}' succeeded")
        return {
            "success": True,
            "result": result,
            "method": method,
        }

    except TypeError as e:
        error_msg = f"Invalid arguments for '{method}': {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "method": method,
        }

    except ValueError as e:
        error_msg = f"Value error in '{method}': {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "method": method,
        }

    except KeyError as e:
        error_msg = f"Method not found: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "method": method,
        }

    except Exception as e:
        error_msg = f"Unexpected error in '{method}': {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": error_msg,
            "method": method,
        }


def dispatch_json(method: str, params_json: str = "[]") -> str:
    """
    JSON-based dispatch for platforms that require string communication
    (e.g., Android JavascriptInterface).

    Args:
        method: Name of the method to call.
        params_json: JSON string of the parameters array.

    Returns:
        JSON string of the result dictionary.
    """
    try:
        params = json.loads(params_json) if params_json else []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON params: {e}")
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON parameters: {str(e)}",
            "method": method,
        })

    result = dispatch(method, params)
    return json.dumps(result, default=str)


def list_methods() -> Dict[str, str]:
    """
    Returns a dictionary of all available methods and their descriptions.
    Delegates to the MethodRegistry.
    """
    _discover_user_handlers()
    return method_registry.list_methods()


def get_schema() -> Dict[str, Any]:
    """
    Returns a full schema of all registered methods with parameter info.
    Useful for generating documentation or client SDKs.
    """
    _discover_user_handlers()
    return method_registry.get_schema()
