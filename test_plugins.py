import sys
import os

# Add the local package to the path so we can test it without installing
sys.path.insert(0, os.path.abspath("."))

from pywebapp.plugins import permissions

def test_permission_catalog():
    print("--- 🔐 Testing Permission Catalog ---")
    print(f"CAMERA: {permissions.CAMERA}")
    print(f"LOCATION: {permissions.LOCATION}")
    print(f"POST_NOTIFICATIONS: {permissions.POST_NOTIFICATIONS}")
    
    assert permissions.CAMERA == "android.permission.CAMERA"
    assert permissions.LOCATION == "android.permission.ACCESS_FINE_LOCATION"
    print("✅ Catalog constants are correct.")

def test_dynamic_listing():
    print("\n--- 🔍 Testing Dynamic Discovery (Mock Mode) ---")
    all_perms = permissions.list_all()
    print(f"Found {len(all_perms)} permissions in mock mode.")
    print(f"Preview: {all_perms[:3]}")
    
    assert "CAMERA" in all_perms
    print("✅ Dynamic discovery logic is working.")

def test_universal_request():
    print("\n--- 🌍 Testing Universal Request (Desktop Fallback) ---")
    result = permissions.request(permissions.CAMERA)
    print(f"Request Result on Desktop: {result}")
    
    assert result is True
    print("✅ Universal fallback is working correctly.")

def test_async_concurrency():
    print("\n--- ⚡ Testing Async Concurrency (Background Loop) ---")
    from pywebapp.core import register, method_registry
    import time

    @register()
    async def async_worker(task_id: int):
        import asyncio
        await asyncio.sleep(1)
        return f"Task {task_id} Done"

    print("Triggering 3 async tasks at once...")
    start_time = time.time()
    
    # We call the registry directly to simulate 3 incoming bridge calls
    # Because they are async, the dispatcher will run them on the background loop
    t1 = threading.Thread(target=method_registry.call, args=("async_worker", [1]))
    t2 = threading.Thread(target=method_registry.call, args=("async_worker", [2]))
    t3 = threading.Thread(target=method_registry.call, args=("async_worker", [3]))

    t1.start(); t2.start(); t3.start()
    t1.join(); t2.join(); t3.join()

    duration = time.time() - start_time
    print(f"All 3 tasks finished in {duration:.2f} seconds.")
    
    # If it was blocking, it would take 3 seconds. 
    # Because it's async, it should take ~1 second!
    assert duration < 2.0
    print("✅ Concurrency confirmed! Tasks ran in parallel.")

import threading

if __name__ == "__main__":
    try:
        test_permission_catalog()
        test_dynamic_listing()
        test_universal_request()
        test_async_concurrency()
        print("\n🏆 ALL TESTS PASSED! Your framework is now ASYNC-POWERED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
