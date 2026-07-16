import json
import requests

API_URL = "http://localhost:8000/gateway/run"

def run_tests():
  with open("tests/sample_runs.json") as f:
   runs = json.load(f)

  for r in runs:
    print("\n--- Running test case ---")
    response = requests.post(API_URL, json=r)
    print("STATUS:", response.status_code)
    print("TEXT:", response.text)


if __name__ == "__main__":
  run_tests()