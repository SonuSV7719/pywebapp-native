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

import asyncio
import threading
import functools
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("pywebapp.registry")

# --- 🚀 Background Event Loop for Async Support ---
_loop = None
_loop_thread = None

def _start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def _get_background_loop():
    global _loop, _loop_thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_start_background_loop, args=(_loop,), daemon=True)
        _loop_thread.start()
        logger.info("Async background loop started.")
    return _loop


class MethodRegistry:
    """
    Central registry for all IPC-callable methods.

    This is the framework's extension point. All Python functions that should
    be callable from JavaScript must be registered here.
    """

    def __init__(self):
        self._methods = {}  # type: Dict[str, Dict[str, Any]]
        self._middleware_pre = []  # type: List[Callable]
        self._middleware_post = []  # type: List[Callable]
        self._lock = threading.RLock()  # 🔒 Thread safety lock for concurrent calls

    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
        namespace: str = "",
    ) -> Callable:
        """
        Decorator to register a function as an IPC-callable method.
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
        """
        with self._lock:
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
                "description": description.strip() or func.__doc__ or "",
                "params": params,
                "module": func.__module__,
            }
            logger.debug(f"Registered method: '{name}'")

    def unregister(self, name: str) -> bool:
        """
        Remove a method from the registry.
        """
        with self._lock:
            if name in self._methods:
                del self._methods[name]
                logger.debug(f"Unregistered method: '{name}'")
                return True
            return False

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """
        Call a registered method by name. Automatically handles both 
        synchronous and asynchronous functions.
        """
        if params is None:
            params = []

        with self._lock:
            if method not in self._methods:
                available = list(self._methods.keys())
                raise KeyError(f"Unknown method: '{method}'. Available: {available}")

            entry = self._methods[method]
            func = entry["function"]
            # 🔒 P1: Snapshot middleware to prevent race conditions
            pre_mw = list(self._middleware_pre)
            post_mw = list(self._middleware_post)

        # Run pre-middleware (outside lock for performance)
        for mw in pre_mw:
            mw(method, params)

        # Execute: Handle Async vs Sync
        if inspect.iscoroutinefunction(func):
            result = self._run_async(func, *params)
        else:
            result = func(*params)

        # Run post-middleware
        for mw in post_mw:
            mw(method, params, result)

        return result

    # Maximum time (seconds) an async handler is allowed to run
    ASYNC_TIMEOUT = 30

    def _run_async(self, func: Callable, *args: Any) -> Any:
        """
        Executes an async function in the dedicated background loop
        and waits for the result with performance tracking.
        """
        import time
        start_time = time.perf_counter()
        
        loop = _get_background_loop()
        future = asyncio.run_coroutine_threadsafe(func(*args), loop)
        try:
            # 🔒 P1: Timeout prevents thread starvation from hanging coroutines
            result = future.result(timeout=self.ASYNC_TIMEOUT)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(
                f"Async handler '{func.__name__}' exceeded {self.ASYNC_TIMEOUT}s timeout"
            )
        
        duration = time.perf_counter() - start_time
        logger.info(f"⚡ Async task '{func.__name__}' took {duration:.4f}s in Python")
        return result

    def has_method(self, name: str) -> bool:
        """Check if a method is registered."""
        with self._lock:
            return name in self._methods

    def list_methods(self) -> Dict[str, str]:
        """
        Returns a dict of {method_name: description} for all registered methods.
        """
        with self._lock:
            return {
                name: entry["description"]
                for name, entry in self._methods.items()
            }

    def get_method_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed info about a registered method (params, types, etc.).
        """
        with self._lock:
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
        """
        with self._lock:
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
        Add a pre-call middleware.
        """
        with self._lock:
            self._middleware_pre.append(func)

    def add_post_middleware(self, func: Callable) -> None:
        """
        Add a post-call middleware.
        """
        with self._lock:
            self._middleware_post.append(func)

    @property
    def method_count(self) -> int:
        """Number of registered methods."""
        with self._lock:
            return len(self._methods)


# ─── Global singleton ────────────────────────────────────────────
# Framework users import this instance and use its @register decorator.
method_registry = MethodRegistry()
register = method_registry.register
