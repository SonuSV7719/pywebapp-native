"""
Python Environment Context.
Stores Android-specific information provided by the native bridge.
Separated from api.py to avoid circular imports.
"""
from typing import Any, Dict

_context: Dict[str, Any] = {}

def set_context(data: Dict[str, Any]) -> None:
    """Set the global context."""
    global _context
    _context = data

def get_context() -> Dict[str, Any]:
    """Retrieve the global context."""
    return _context
