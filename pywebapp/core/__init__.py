"""
PyWebApp Core — The engine behind the framework.

Public API:
    from pywebapp.core import register, get_logger, dispatch, dispatch_json

All framework users need is the @register decorator to expose their functions.
"""

from .registry import method_registry, register
from .api import dispatch, dispatch_json, set_context, get_context, list_methods, get_schema
from .logger import get_logger
from .context import set_context as _set_ctx, get_context as _get_ctx

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
]
