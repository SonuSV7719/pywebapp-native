"""
PyWebApp Core — The engine behind the framework.

Public API:
    from pywebapp.core import register, get_logger, dispatch, dispatch_json
    
All framework users need is the @register decorator to expose their functions.
"""

from .registry import method_registry, register
from .api import dispatch, dispatch_json, list_methods, get_schema, hide_splash
from .context import get_context, set_context
from .logger import get_logger

__all__ = [
    "method_registry",
    "register",
    "dispatch",
    "dispatch_json",
    "set_context",
    "get_context",
    "list_methods",
    "get_schema",
    "get_logger",
    "hide_splash",
]
