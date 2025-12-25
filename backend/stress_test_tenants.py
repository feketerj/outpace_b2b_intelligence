#!/usr/bin/env python3
"""
Stress Test: Tenant Onboarding
Creates 20 tenants, 2 users each, 50 opportunities each
Measures timing and verifies isolation
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = None

# Results storage
results = {
    "tenant_times": [],
    "user_times": [],
    "opp_times": [],
    "tenants_created": [],
    "users_created": [],
    "verifications": {},
    "errors": []
}

def login_admin():
    global ADMIN_TOKEN
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@outpace.ai",
        "password": "Admin123!"
    })
    if resp.status_code != 200:
        raise Exception(f"Admin login failed: {resp.text}")
    ADMIN_TOKEN = resp.json()["access_token"]
    return ADMIN_TOKEN

def headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}

def create_tenant(n):
    """Create tenant scale-test-{n}"""
    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/tenants", headers=headers(), json={
        "name": f"Scale Test {n}",
        "slug": f"scale-test-{n}"
    })
    elapsed_ms = (time.perf_counter() - start) * 1000

    if resp.status_code not in [200, 201]:
        results["errors"].append(f"Tenant {n}: {resp.status_code} - {resp.text}")
        return None, elapsed_ms

    data = resp.json()
    return data, elapsed_ms

def create_user(tenant_id, tenant_n, user_m):
    """Create user{m}@scale-test-{n}.com"""
    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/users", headers=headers(), json={
        "email": f"user{user_m}@scale-test-{tenant_n}.com",
        "password": "TestPass123!",
        "full_name": f"User {user_m} Tenant {tenant_n}",
        "role": "tenant_user",
        "tenant_id": tenant_id
    })
    elapsed_ms = (time.perf_counter() - start) * 1000

    if resp.status_code not in [200, 201]:
        results["errors"].append(f"User {user_m}@tenant-{tenant_n}: {resp.status_code} - {resp.text}")
        return None, elapsed_ms

    return resp.json(), elapsed_ms

def create_opportunity(tenant_id, tenant_n, opp_n):
    """Create opportunity for tenant"""
    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/opportunities", headers=headers(), json={
        "external_id": f"scale-opp-{tenant_n}-{opp_n}",
        "tenant_id": tenant_id,
        "title": f"Scale Test Opportunity {opp_n}",
        "description": f"Opportunity {opp_n} for scale-test-{tenant_n}",
        "agency": "Scale Test Agency"
    })
    elapsed_ms = (time.perf_counter() - start) * 1000

    if resp.status_code not in [200, 201]:
        results["errors"].append(f"Opp {opp_n}@tenant-{tenant_n}: {resp.status_code} - {resp.text[:100]}")
        return None, elapsed_ms

    return resp.json(), elapsed_ms

def verify_tenant_count():
    """GET /api/tenants should return 22 total"""
    resp = requests.get(f"{BASE_URL}/api/tenants", headers=headers())
    data = resp.json()
    total = data["pagination"]["total"]
    passed = total == 22
    return {
        "test": "Tenant count == 22",
        "passed": passed,
        "actual": total,
        "evidence": f"pagination.total = {total}"
    }

def verify_users_per_tenant(tenant_id, tenant_n):
    """Each tenant should have exactly 2 users"""
    resp = requests.get(f"{BASE_URL}/api/users", headers=headers(), params={"tenant_id": tenant_id})
    data = resp.json()
    # Filter users for this tenant
    users = [u for u in data.get("data", []) if u.get("tenant_id") == tenant_id]
    return len(users) == 2, len(users)

def verify_opportunities_per_tenant(tenant_id, tenant_n):
    """Each tenant should have exactly 50 opportunities"""
    # Need to login as tenant user to check
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": f"user1@scale-test-{tenant_n}.com",
        "password": "TestPass123!"
    })
    if resp.status_code != 200:
        return False, f"Login failed: {resp.text[:50]}"

    token = resp.json()["access_token"]
    resp = requests.get(f"{BASE_URL}/api/opportunities",
                       headers={"Authorization": f"Bearer {token}"},
                       params={"per_page": 100})
    data = resp.json()
    total = data["pagination"]["total"]
    return total == 50, total

def verify_isolation(tenant_7_id, tenant_15_id):
    """User from tenant-15 cannot see tenant-7 opportunities"""
    # Login as user from tenant-15
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user1@scale-test-15.com",
        "password": "TestPass123!"
    })
    if resp.status_code != 200:
        return {"passed": False, "evidence": f"Login failed: {resp.text}"}

    token = resp.json()["access_token"]

    # Try to list opportunities (should only see tenant-15's)
    resp = requests.get(f"{BASE_URL}/api/opportunities",
                       headers={"Authorization": f"Bearer {token}"})
    data = resp.json()

    # Check that none belong to tenant-7
    tenant_7_opps = [o for o in data.get("data", []) if o.get("tenant_id") == tenant_7_id]

    return {
        "passed": len(tenant_7_opps) == 0,
        "evidence": f"User15 sees {len(data.get('data',[]))} opps, {len(tenant_7_opps)} from tenant-7"
    }

def measure_list_performance(tenant_id, tenant_n):
    """List opportunities for tenant with 50 opps should be < 500ms"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": f"user1@scale-test-{tenant_n}.com",
        "password": "TestPass123!"
    })
    token = resp.json()["access_token"]

    start = time.perf_counter()
    resp = requests.get(f"{BASE_URL}/api/opportunities",
                       headers={"Authorization": f"Bearer {token}"},
                       params={"per_page": 100})
    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "passed": elapsed_ms < 500,
        "elapsed_ms": round(elapsed_ms, 2),
        "evidence": f"List 50 opps took {elapsed_ms:.2f}ms"
    }

def cleanup():
    """Delete all scale-test-* tenants and their data"""
    print("\n=== CLEANUP ===")

    # Get all tenants
    resp = requests.get(f"{BASE_URL}/api/tenants", headers=headers(), params={"per_page": 100})
    tenants = resp.json().get("data", [])

    deleted = 0
    for t in tenants:
        if t["slug"].startswith("scale-test-"):
            # Delete users first
            resp = requests.get(f"{BASE_URL}/api/users", headers=headers())
            users = [u for u in resp.json().get("data", []) if u.get("tenant_id") == t["id"]]
            for u in users:
                requests.delete(f"{BASE_URL}/api/users/{u['id']}", headers=headers())

            # Delete opportunities
            resp = requests.get(f"{BASE_URL}/api/opportunities", headers=headers(),
                              params={"tenant_id": t["id"], "per_page": 100})
            opps = resp.json().get("data", [])
            for o in opps:
                requests.delete(f"{BASE_URL}/api/opportunities/{o['id']}", headers=headers())

            # Delete tenant
            requests.delete(f"{BASE_URL}/api/tenants/{t['id']}", headers=headers())
            deleted += 1

    print(f"Deleted {deleted} test tenants")
    return deleted

def main():
    print("=" * 60)
    print("STRESS TEST: Tenant Onboarding")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    total_start = time.perf_counter()

    # Login
    login_admin()
    print("\n[1/6] Admin authenticated")

    # Create 20 tenants
    print("\n[2/6] Creating 20 tenants...")
    for n in range(1, 21):
        tenant, ms = create_tenant(n)
        results["tenant_times"].append({"n": n, "ms": round(ms, 2)})
        if tenant:
            results["tenants_created"].append({"n": n, "id": tenant["id"], "slug": tenant["slug"]})
            print(f"  Tenant {n}: {ms:.1f}ms - {tenant['id']}")

    # Create 2 users per tenant
    print("\n[3/6] Creating 2 users per tenant (40 total)...")
    for t in results["tenants_created"]:
        for m in range(1, 3):
            user, ms = create_user(t["id"], t["n"], m)
            results["user_times"].append({"tenant": t["n"], "user": m, "ms": round(ms, 2)})
            if user:
                results["users_created"].append({
                    "tenant_n": t["n"],
                    "user_m": m,
                    "id": user["id"],
                    "email": user["email"]
                })
    print(f"  Created {len(results['users_created'])} users")

    # Create 50 opportunities per tenant
    print("\n[4/6] Creating 50 opportunities per tenant (1000 total)...")
    opp_count = 0
    for t in results["tenants_created"]:
        for o in range(1, 51):
            opp, ms = create_opportunity(t["id"], t["n"], o)
            results["opp_times"].append({"tenant": t["n"], "opp": o, "ms": round(ms, 2)})
            if opp:
                opp_count += 1
        print(f"  Tenant {t['n']}: 50 opportunities created")
    print(f"  Total opportunities: {opp_count}")

    total_creation_time = time.perf_counter() - total_start

    # Verifications
    print("\n[5/6] Running verifications...")

    # Verify tenant count
    v = verify_tenant_count()
    results["verifications"]["tenant_count"] = v
    print(f"  Tenant count == 22: {'PASS' if v['passed'] else 'FAIL'} ({v['actual']})")

    # Verify users per tenant (sample: tenant 5, 10, 15)
    for n in [5, 10, 15]:
        t = next((x for x in results["tenants_created"] if x["n"] == n), None)
        if t:
            passed, count = verify_users_per_tenant(t["id"], n)
            results["verifications"][f"users_tenant_{n}"] = {"passed": passed, "count": count}
            print(f"  Tenant {n} has 2 users: {'PASS' if passed else 'FAIL'} ({count})")

    # Verify opportunities per tenant (sample)
    for n in [5, 10, 15]:
        t = next((x for x in results["tenants_created"] if x["n"] == n), None)
        if t:
            passed, count = verify_opportunities_per_tenant(t["id"], n)
            results["verifications"][f"opps_tenant_{n}"] = {"passed": passed, "count": count}
            print(f"  Tenant {n} has 50 opps: {'PASS' if passed else 'FAIL'} ({count})")

    # Verify isolation
    t7 = next((x for x in results["tenants_created"] if x["n"] == 7), None)
    t15 = next((x for x in results["tenants_created"] if x["n"] == 15), None)
    if t7 and t15:
        iso = verify_isolation(t7["id"], t15["id"])
        results["verifications"]["isolation_15_vs_7"] = iso
        print(f"  Isolation (user15 can't see tenant7): {'PASS' if iso['passed'] else 'FAIL'}")
        print(f"    {iso['evidence']}")

    # Performance test
    if t15:
        perf = measure_list_performance(t15["id"], 15)
        results["verifications"]["list_performance"] = perf
        print(f"  List 50 opps < 500ms: {'PASS' if perf['passed'] else 'FAIL'} ({perf['elapsed_ms']}ms)")

    print("\n[6/6] Cleanup...")
    cleanup()

    # Final report
    total_time = time.perf_counter() - total_start

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    # Timing table
    print("\n### Creation Times")
    print(f"{'Item':<30} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}")
    print("-" * 66)

    if results["tenant_times"]:
        times = [t["ms"] for t in results["tenant_times"]]
        print(f"{'Tenant creation':<30} {sum(times)/len(times):<12.2f} {min(times):<12.2f} {max(times):<12.2f}")

    if results["user_times"]:
        times = [t["ms"] for t in results["user_times"]]
        print(f"{'User creation':<30} {sum(times)/len(times):<12.2f} {min(times):<12.2f} {max(times):<12.2f}")

    if results["opp_times"]:
        times = [t["ms"] for t in results["opp_times"]]
        print(f"{'Opportunity creation':<30} {sum(times)/len(times):<12.2f} {min(times):<12.2f} {max(times):<12.2f}")

    print(f"\n{'Total creation time:':<30} {total_creation_time:.2f} seconds")
    print(f"{'Total test time (incl cleanup):':<30} {total_time:.2f} seconds")

    # Verification results
    print("\n### Verification Results")
    print(f"{'Test':<45} {'Result':<10}")
    print("-" * 55)
    for name, v in results["verifications"].items():
        status = "PASS" if v.get("passed") else "FAIL"
        print(f"{name:<45} {status:<10}")

    # Errors
    if results["errors"]:
        print(f"\n### Errors ({len(results['errors'])})")
        for e in results["errors"][:10]:
            print(f"  - {e}")
        if len(results["errors"]) > 10:
            print(f"  ... and {len(results['errors'])-10} more")

    # Final status
    all_passed = all(v.get("passed", False) for v in results["verifications"].values())
    print("\n" + "=" * 60)
    print(f"FINAL STATUS: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 60)

    return results

if __name__ == "__main__":
    main()
