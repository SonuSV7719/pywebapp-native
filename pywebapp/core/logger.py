"""
Cross-platform logging utility.
Provides a rotating file logger with console output.
Automatically selects platform-appropriate log directories.
"""

import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler


def _get_log_directory() -> str:
    """
    Returns the platform-appropriate log directory.
    - Windows: %APPDATA%/PyWebApp/logs
    - macOS:   ~/Library/Logs/PyWebApp
    - Linux:   ~/.local/share/PyWebApp/logs
    - Android: Falls back to current directory (Chaquopy handles storage)
    """
    system = platform.system()

    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "PyWebApp", "logs")
    elif system == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Logs", "PyWebApp")
    elif system == "Linux":
        # Check if running on Android (Chaquopy sets specific env)
        if hasattr(sys, "getandroidapilevel"):
            return os.path.join(os.getcwd(), "logs")
        xdg_data = os.environ.get(
            "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
        )
        return os.path.join(xdg_data, "PyWebApp", "logs")
    else:
        return os.path.join(os.getcwd(), "logs")


def get_logger(
    name: str = "pywebapp",
    level: int = logging.DEBUG,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Creates and returns a configured logger instance.

    Args:
        name: Logger name (used for both logger identity and log filename).
        level: Logging level (default: DEBUG).
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to keep.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (with graceful fallback if directory creation fails)
    try:
        log_dir = _get_log_directory()
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{name}.log")

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.debug(f"Log file initialized at: {log_file}")
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not create file logger: {e}. Using console only.")

    return logger
