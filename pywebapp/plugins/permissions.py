"""
Universal Permission Plugin — Handle Android runtime permissions directly from Python.

This module provides a Hybrid approach:
1. Pre-defined constants for common permissions (for IDE autocomplete).
2. Dynamic discovery to fetch every permission the device supports.
3. Universal request() function.
"""

import os
import platform
import json
from typing import TYPE_CHECKING, List, Dict, Any, Optional

# For IDE suggestions on Windows
if TYPE_CHECKING:
    from android.Manifest import permission as AndroidPermission # type: ignore
    from com.chaquo.python import Python # type: ignore

# --- 1. THE PERMISSION CATALOG (Static for Autocomplete) ---

# 📸 Media & Camera
CAMERA = "android.permission.CAMERA"
MICROPHONE = "android.permission.RECORD_AUDIO"
RECORD_AUDIO = "android.permission.RECORD_AUDIO"
ACCESS_MEDIA_LOCATION = "android.permission.ACCESS_MEDIA_LOCATION" # API 29+

# 📍 Location
LOCATION = "android.permission.ACCESS_FINE_LOCATION"
LOCATION_COARSE = "android.permission.ACCESS_COARSE_LOCATION"
LOCATION_BACKGROUND = "android.permission.ACCESS_BACKGROUND_LOCATION" # API 29+

# 📁 Storage
STORAGE_READ = "android.permission.READ_EXTERNAL_STORAGE"
STORAGE_WRITE = "android.permission.WRITE_EXTERNAL_STORAGE"
MANAGE_EXTERNAL_STORAGE = "android.permission.MANAGE_EXTERNAL_STORAGE" # API 30+
READ_MEDIA_IMAGES = "android.permission.READ_MEDIA_IMAGES"             # API 33+
READ_MEDIA_VIDEO = "android.permission.READ_MEDIA_VIDEO"               # API 33+
READ_MEDIA_AUDIO = "android.permission.READ_MEDIA_AUDIO"               # API 33+

# 👤 Contacts & Calendar
CONTACTS_READ = "android.permission.READ_CONTACTS"
CONTACTS_WRITE = "android.permission.WRITE_CONTACTS"
GET_ACCOUNTS = "android.permission.GET_ACCOUNTS"
CALENDAR_READ = "android.permission.READ_CALENDAR"
CALENDAR_WRITE = "android.permission.WRITE_CALENDAR"

# 💬 SMS & Messages
SMS_SEND = "android.permission.SEND_SMS"
SMS_RECEIVE = "android.permission.RECEIVE_SMS"
SMS_READ = "android.permission.READ_SMS"
RECEIVE_MMS = "android.permission.RECEIVE_MMS"
RECEIVE_WAP_PUSH = "android.permission.RECEIVE_WAP_PUSH"

# 📞 Phone & Calls
CALL_PHONE = "android.permission.CALL_PHONE"
READ_PHONE_STATE = "android.permission.READ_PHONE_STATE"
READ_PHONE_NUMBERS = "android.permission.READ_PHONE_NUMBERS" # API 26+
READ_CALL_LOG = "android.permission.READ_CALL_LOG"
WRITE_CALL_LOG = "android.permission.WRITE_CALL_LOG"
ANSWER_PHONE_CALLS = "android.permission.ANSWER_PHONE_CALLS" # API 26+
ADD_VOICEMAIL = "com.android.voicemail.permission.ADD_VOICEMAIL"

# 📶 Connectivity (Bluetooth/WiFi)
BLUETOOTH = "android.permission.BLUETOOTH"
BLUETOOTH_ADMIN = "android.permission.BLUETOOTH_ADMIN"
BLUETOOTH_CONNECT = "android.permission.BLUETOOTH_CONNECT"   # API 31+
BLUETOOTH_SCAN = "android.permission.BLUETOOTH_SCAN"         # API 31+
BLUETOOTH_ADVERTISE = "android.permission.BLUETOOTH_ADVERTISE" # API 31+
NFC = "android.permission.NFC"
INTERNET = "android.permission.INTERNET"
NETWORK_STATE = "android.permission.ACCESS_NETWORK_STATE"
WIFI_STATE = "android.permission.ACCESS_WIFI_STATE"

# 🛠️ System & Hardware
VIBRATE = "android.permission.VIBRATE"
BATTERY_STATS = "android.permission.BATTERY_STATS"
WAKE_LOCK = "android.permission.WAKE_LOCK"
POST_NOTIFICATIONS = "android.permission.POST_NOTIFICATIONS" # API 33+
FOREGROUND_SERVICE = "android.permission.FOREGROUND_SERVICE" # API 28+
USE_BIOMETRIC = "android.permission.USE_BIOMETRIC"           # API 28+
USE_FINGERPRINT = "android.permission.USE_FINGERPRINT"
ACTIVITY_RECOGNITION = "android.permission.ACTIVITY_RECOGNITION" # API 29+
BODY_SENSORS = "android.permission.BODY_SENSORS"
SET_ALARM = "com.android.alarm.permission.SET_ALARM"
SET_WALLPAPER = "android.permission.SET_WALLPAPER"
RECEIVE_BOOT_COMPLETED = "android.permission.RECEIVE_BOOT_COMPLETED"
SYSTEM_ALERT_WINDOW = "android.permission.SYSTEM_ALERT_WINDOW" # Overlay

# 🌐 Legacy/Other
READ_HISTORY_BOOKMARKS = "com.android.browser.permission.READ_HISTORY_BOOKMARKS"
WRITE_HISTORY_BOOKMARKS = "com.android.browser.permission.WRITE_HISTORY_BOOKMARKS"

def _is_android() -> bool:
    return "ANDROID_STORAGE" in os.environ

import threading

_request_event = threading.Event()
_last_result = False

def _on_permission_result(granted: bool):
    """Internal callback called by the bridge when the user responds."""
    global _last_result
    _last_result = granted
    _request_event.set()

def request(permission: str) -> bool:
    """
    Request a specific Android permission at runtime.
    This call blocks until the user clicks 'Allow' or 'Deny'.
    """
    if not _is_android():
        return True

    from com.chaquo.python import Python # type: ignore
    try:
        # 1. Get the current Activity
        activity = Python.getPlatform().getApplication()
        
        # 2. Reset the event
        _request_event.clear()
        
        # 3. Trigger the real Android popup
        # Note: We use the existing MainActivity method we just created
        activity.requestRuntimePermission(permission, "internal_python_callback")
        
        # 4. Wait for the user (Max 60 seconds)
        # The bridge will call _on_permission_result via the api dispatcher
        _request_event.wait(timeout=60.0)
        
        return _last_result
    except Exception as e:
        print(f"Permission request error: {e}")
        return False

def list_all() -> List[str]:
    """
    DYNAMIC DISCOVERY: Fetches the 100% complete list of permissions 
    directly from the Android OS using Java Reflection.
    """
    if not _is_android():
        return ["CAMERA", "LOCATION", "STORAGE"] # Mock list for desktop

    try:
        from android.Manifest import permission as AndroidPermission # type: ignore
        # Use Python's dir() on the Java class to see all constants
        all_attrs = dir(AndroidPermission)
        # Filter for only the permission strings (ALL_CAPS constants)
        return [attr for attr in all_attrs if attr.isupper() and not attr.startswith("_")]
    except Exception as e:
        print(f"Failed to list dynamic permissions: {e}")
        return [CAMERA, LOCATION, STORAGE_WRITE]

def get_status(permission: str) -> bool:
    """Check if a permission is already granted without showing a popup."""
    if not _is_android():
        return True
        
    try:
        from com.chaquo.python import Python # type: ignore
        from androidx.core.content import ContextCompat # type: ignore
        from android.content.pm import PackageManager # type: ignore
        
        context = Python.getPlatform().getApplication()
        status = ContextCompat.checkSelfPermission(context, permission)
        return status == PackageManager.PERMISSION_GRANTED
    except Exception:
        return False
