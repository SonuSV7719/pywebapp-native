"""
Python Environment Context.
Stores Android-specific information provided by the native bridge.
Separated from api.py to avoid circular imports.
"""
from typing import Any, Dict

_context = {}  # type: Dict[str, Any]
_activity = None # type: Any (MainActivity instance on Android)

def set_context(data: Dict[str, Any]) -> None:
    """Set the global data context."""
    global _context
    _context = data

def get_context() -> Dict[str, Any]:
    """Retrieve the global data context."""
    return _context

def set_activity(activity: Any) -> None:
    """Set the native Activity instance."""
    global _activity
    _activity = activity

def get_activity() -> Any:
    """Retrieve the native Activity instance."""
    return _activity
