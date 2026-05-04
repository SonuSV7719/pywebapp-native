"""
Method Registry — The core abstraction layer of the PyWebApp framework.

Provides a decorator-based system for registering Python functions as IPC-callable
methods. Framework users only need to:

    from pywebapp.core import register

    @register("greet", description="Say hello")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

The registry is automatically discovered by the API dispatcher.

Design goals:
    - Zero boilerplate: one decorator to expose a function
    - Introspectable: list all methods, descriptions, and signatures
    - Middleware-ready: pre/post hooks for logging, auth, caching
    - Namespace support: group methods by module (e.g., "math.add", "data.process")
    - Validation: optional parameter type checking
"""

import functools
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("pywebapp.registry")


class MethodRegistry:
    """
    Central registry for all IPC-callable methods.

    This is the framework's extension point. All Python functions that should
    be callable from JavaScript must be registered here.

    Usage:
        registry = MethodRegistry()

        @registry.register("add", description="Add two numbers")
        def add(a, b):
            return a + b

        # Or register without decorator:
        registry.register_function("subtract", subtract, description="Subtract")

        # Call:
        result = registry.call("add", [5, 7])  # → 12
    """

    def __init__(self):
        self._methods = {}  # type: Dict[str, Dict[str, Any]]
        self._middleware_pre = []  # type: List[Callable]
        self._middleware_post = []  # type: List[Callable]

    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
        namespace: str = "",
    ) -> Callable:
        """
        Decorator to register a function as an IPC-callable method.

        Args:
            name: Method name for IPC calls. Defaults to function name.
            description: Human-readable description (for introspection/docs).
            namespace: Optional namespace prefix (e.g., "math" → "math.add").

        Returns:
            Decorator function.

        Example:
            @registry.register(description="Add two numbers")
            def add(a, b):
                return a + b

            @registry.register("custom_name", namespace="utils")
            def my_func():
                pass
            # Registered as "utils.custom_name"
        """
        def decorator(func: Callable) -> Callable:
            method_name = name or func.__name__
            full_name = f"{namespace}.{method_name}" if namespace else method_name

            self.register_function(full_name, func, description=description or func.__doc__ or "")

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def register_function(
        self,
        name: str,
        func: Callable,
        description: str = "",
    ) -> None:
        """
        Register a function directly (without decorator).

        Args:
            name: Method name for IPC calls.
            func: The callable to register.
            description: Human-readable description.
        """
        if name in self._methods:
            logger.warning(f"Overwriting existing method: '{name}'")

        # Extract signature info for introspection
        sig = inspect.signature(func)
        params = []
        for param_name, param in sig.parameters.items():
            param_info = {"name": param_name}
            if param.annotation != inspect.Parameter.empty:
                param_info["type"] = param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation)
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            params.append(param_info)

        self._methods[name] = {
            "function": func,
            "description": description.strip(),
            "params": params,
            "module": func.__module__,
        }

        logger.debug(f"Registered method: '{name}' ({description})")

    def unregister(self, name: str) -> bool:
        """
        Remove a method from the registry.

        Args:
            name: Method name to remove.

        Returns:
            True if the method was removed, False if it didn't exist.
        """
        if name in self._methods:
            del self._methods[name]
            logger.debug(f"Unregistered method: '{name}'")
            return True
        return False

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """
        Call a registered method by name.

        Args:
            method: Name of the method.
            params: List of positional arguments.

        Returns:
            Return value of the called function.

        Raises:
            KeyError: If method is not registered.
            TypeError: If wrong number/type of arguments.
        """
        if params is None:
            params = []

        if method not in self._methods:
            available = list(self._methods.keys())
            raise KeyError(f"Unknown method: '{method}'. Available: {available}")

        entry = self._methods[method]
        func = entry["function"]

        # Run pre-middleware
        for mw in self._middleware_pre:
            mw(method, params)

        # Execute
        result = func(*params)

        # Run post-middleware
        for mw in self._middleware_post:
            mw(method, params, result)

        return result

    def has_method(self, name: str) -> bool:
        """Check if a method is registered."""
        return name in self._methods

    def list_methods(self) -> Dict[str, str]:
        """
        Returns a dict of {method_name: description} for all registered methods.
        """
        return {
            name: entry["description"]
            for name, entry in self._methods.items()
        }

    def get_method_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed info about a registered method (params, types, etc.).

        Returns:
            Dict with keys: description, params, module. None if not found.
        """
        entry = self._methods.get(name)
        if entry is None:
            return None

        return {
            "description": entry["description"],
            "params": entry["params"],
            "module": entry["module"],
        }

    def get_schema(self) -> Dict[str, Any]:
        """
        Returns a full schema of all registered methods.
        Useful for generating documentation or client SDKs.
        """
        schema = {}
        for name, entry in self._methods.items():
            schema[name] = {
                "description": entry["description"],
                "params": entry["params"],
                "module": entry["module"],
            }
        return schema

    def add_pre_middleware(self, func: Callable) -> None:
        """
        Add a pre-call middleware. Called as middleware(method, params) before execution.
        """
        self._middleware_pre.append(func)

    def add_post_middleware(self, func: Callable) -> None:
        """
        Add a post-call middleware. Called as middleware(method, params, result) after execution.
        """
        self._middleware_post.append(func)

    @property
    def method_count(self) -> int:
        """Number of registered methods."""
        return len(self._methods)


# ─── Global singleton ────────────────────────────────────────────
# Framework users import this instance and use its @register decorator.
method_registry = MethodRegistry()
register = method_registry.register
