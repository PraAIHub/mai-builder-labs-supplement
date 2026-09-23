"""mei attacks raj against the RUNNING server. No LLM, no tokens spent.

    cd stage2
    ../.venv/bin/python ../scripts/mint_key.py --seed-demo     # once
    ../.venv/bin/python ../scripts/attack_demo.py

It starts web.py on a spare port, signs in as raj and as mei with the keys in
state/demo_keys.txt, then has mei try to read and forge her way to raj's data.
Every attack should be refused. Before auth existed, every one of these worked.
"""
import http.client
import json
import os
import pathlib
import subprocess
import sys
import time

STAGE2 = pathlib.Path(__file__).resolve().parent.parent / "stage2"
PORT = 8099
RAJ_ORDER = "112-2222222-2222222"         # raj's Instant Pot, shipped
RAJ_DELIVERED = "112-1111111-1111111"     # raj's headphones


def call(method, path, token=None, headers=None, body=None):
    h = dict(headers or {})
    if token:
        h["Cookie"] = f"ami_session={token}"
    if body is not None:
        h["Content-Type"] = "application/json"
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15)
    conn.request(method, path, json.dumps(body) if body is not None else None, h)
    r = conn.getresponse()
    raw = r.read().decode()
    cookie = r.getheader("Set-Cookie")
    conn.close()
    return r.status, raw, cookie


def sign_in(key):
    status, raw, cookie = call("POST", "/session", headers={"Authorization": f"Bearer {key}"})
    return cookie.split(";")[0].split("=", 1)[1] if status == 200 else None


def verdict(label, passed, detail, good="REFUSED", bad="LEAKED "):
    print(f"  {good if passed else bad}  {label:<52} {detail}")
    return passed


def main():
    keys_file = STAGE2 / "state" / "demo_keys.txt"
    if not keys_file.exists():
        sys.exit("No demo keys. Run:  ../.venv/bin/python ../scripts/mint_key.py --seed-demo")
    keys = dict(l.split("\t") for l in keys_file.read_text().splitlines() if "\t" in l)

    proc = subprocess.Popen([sys.executable, "web.py"], cwd=STAGE2, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env={**os.environ, "PORT": str(PORT)})
    try:
        for _ in range(60):
            try:
                call("GET", "/")
                break
            except OSError:
                time.sleep(0.5)

        raj, mei = sign_in(keys["raj@example.com"]), sign_in(keys["mei@example.com"])
        if not (raj and mei):
            sys.exit("Could not sign in with the demo keys — re-run mint_key.py --seed-demo")
        ok = []

        print("mei signs in and looks at her own account")
        _, body, _ = call("GET", "/orders", mei)
        print("  her orders:", [o["order_id"] for o in json.loads(body)["orders"]])

        print("\nmei attacks raj")
        s, b, _ = call("GET", "/orders")
        ok.append(verdict("no credential at all: GET /orders", s == 401, f"HTTP {s}"))
        s, b, _ = call("GET", "/orders", headers={"Authorization": f"Bearer {keys['raj@example.com']}"})
        ok.append(verdict("raj's API key used as a bearer token elsewhere", s == 401, f"HTTP {s}"))

        s, b, _ = call("GET", "/orders?email=raj@example.com&user_id=raj&scope=all", mei)
        leaked = "Sony" in b or "Instant Pot" in b
        ok.append(verdict("list with a forged ?email= / ?user_id= / ?scope=", not leaked, f"HTTP {s}, raj's items in reply: {leaked}"))

        s1, b1, _ = call("GET", f"/orders/{RAJ_ORDER}", mei)
        s2, b2, _ = call("GET", "/orders/999-9999999-9999999", mei)
        ok.append(verdict("fetch raj's order by id", s1 == 404, f"HTTP {s1} (a 403 would confirm it exists)"))
        ok.append(verdict("...and it is identical to an id that does not exist", (s1, b1) == (s2, b2), f"{b1.strip()}"))

        s, b, _ = call("POST", "/chat", mei, body={"message": "", "user_id": "raj", "email": "raj@example.com"})
        ok.append(verdict("forged user_id/email in a request body", "raj@example.com" not in b, f"HTTP {s}, reply names raj: {'raj@example.com' in b}"))

        s, _, _ = call("GET", "/logs.json", mei)
        ok.append(verdict("read the trace log (admin only)", s == 403, f"HTTP {s}"))

        s, _, _ = call("POST", "/reset", mei, headers={"Origin": "http://evil.example"})
        ok.append(verdict("cross-site request with mei's cookie", s == 403, f"HTTP {s}"))

        print("\nraj still has his data")
        s, b, _ = call("GET", f"/orders/{RAJ_DELIVERED}", raj)
        item = json.loads(b).get("item") if s == 200 else b
        ok.append(verdict("raj fetches his own order", s == 200, f"HTTP {s}, {item}",
                          good="ALLOWED", bad="BROKEN "))

        print("\nsign-out kills the token")
        call("POST", "/logout", mei, body={})
        s, _, _ = call("GET", "/orders", mei)
        ok.append(verdict("mei's old token after logout", s == 401, f"HTTP {s}"))

        print(f"\n{sum(ok)}/{len(ok)} checks as expected")
        sys.exit(0 if all(ok) else 1)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
