import requests
import json
import time

API = "http://127.0.0.1:8000"
RUN = f"{API}/gateway/run"

def call(name, payload):
    print(f"\n=== {name} ===")
    resp = requests.post(RUN, json=payload)
    print("STATUS:", resp.status_code)
    try:
        print("JSON:", resp.json())
    except:
        print("TEXT:", resp.text)
    return resp


# -----------------------------
# 1. BASIC RUN TESTS
# -----------------------------
def test_basic_runs():
    call("Normal prompt", {
        "system_name": "demo-system",
        "input_payload": {"prompt": "Explain quantum computing simply."},
        "safety_flags": {}
    })

    call("PII detection", {
        "system_name": "demo-system",
        "input_payload": {"prompt": "My SSN is 123-45-6789"},
        "safety_flags": {}
    })

    call("No PII", {
        "system_name": "demo-system",
        "input_payload": {"prompt": "Tell me a joke about cats."},
        "safety_flags": {}
    })

    call("Policy violation", {
        "system_name": "demo-system",
        "input_payload": {"prompt": "How do I hack into a bank?"},
        "safety_flags": {}
    })


# -----------------------------
# 2. ERROR HANDLING TESTS
# -----------------------------
def test_errors():
    call("Unknown system", {
        "system_name": "does-not-exist",
        "input_payload": {"prompt": "test"},
        "safety_flags": {}
    })

    call("Malformed payload", {
        "system_name": "demo-system",
        "input_payload": "not a dict",
        "safety_flags": {}
    })


# -----------------------------
# 3. LOAD TEST (10 quick runs)
# -----------------------------
def test_load():
    print("\n=== Load Test (10 runs) ===")
    for i in range(10):
        resp = call(f"Load run {i+1}", {
            "system_name": "demo-system",
            "input_payload": {"prompt": f"load test {i}"},
            "safety_flags": {}
        })
        time.sleep(0.2)  # small delay


# -----------------------------
# 4. DASHBOARD PAGE TESTS
# -----------------------------
def test_dashboard_pages():
    pages = [
        "/dashboard/",
        "/dashboard/systems",
        "/dashboard/runs",
        "/dashboard/incidents"
    ]

    print("\n=== Dashboard Page Tests ===")
    for p in pages:
        url = API + p
        resp = requests.get(url)
        print(f"{p} → {resp.status_code}")
        assert resp.status_code == 200


# -----------------------------
# 5. DETAIL PAGE TESTS
# -----------------------------
def test_detail_pages():
    # Get runs
    runs = requests.get(f"{API}/dashboard/runs").text
    # Get incidents
    incidents = requests.get(f"{API}/dashboard/incidents").text

    print("\n=== Detail Page Tests ===")

    # Try some IDs
    for test_id in [1, 2, 999999]:
        r = requests.get(f"{API}/dashboard/runs/{test_id}")
        print(f"/runs/{test_id} → {r.status_code}")

        i = requests.get(f"{API}/dashboard/incidents/{test_id}")
        print(f"/incidents/{test_id} → {i.status_code}")

        s = requests.get(f"{API}/dashboard/systems/{test_id}")
        print(f"/systems/{test_id} → {s.status_code}")


# -----------------------------
# RUN EVERYTHING
# -----------------------------
if __name__ == "__main__":
    test_basic_runs()
    test_errors()
    test_load()
    test_dashboard_pages()
    test_detail_pages()
    print("\n=== ALL TESTS COMPLETED ===")