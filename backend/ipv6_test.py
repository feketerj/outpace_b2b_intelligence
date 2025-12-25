import requests
import time

# Test 1: localhost (what we've been using)
print("Testing localhost...")
start = time.time()
requests.get("http://localhost:8000/health")
print(f"localhost: {(time.time()-start)*1000:.0f}ms")

# Test 2: 127.0.0.1 (explicit IPv4)
print("Testing 127.0.0.1...")
start = time.time()
requests.get("http://127.0.0.1:8000/health")
print(f"127.0.0.1: {(time.time()-start)*1000:.0f}ms")

# Test 3: ::1 (explicit IPv6)
print("Testing ::1 (IPv6)...")
try:
    start = time.time()
    requests.get("http://[::1]:8000/health", timeout=5)
    print(f"::1: {(time.time()-start)*1000:.0f}ms")
except Exception as e:
    elapsed = (time.time()-start)*1000
    print(f"::1: FAILED after {elapsed:.0f}ms - {type(e).__name__}")
