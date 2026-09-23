"""Issue, rotate, revoke and list Ami API keys. Run by an admin, not a user.

    cd stage2
    ../.venv/bin/python ../scripts/mint_key.py --create mei@example.com --name Mei
    ../.venv/bin/python ../scripts/mint_key.py --create boss@example.com --name Boss --admin
    ../.venv/bin/python ../scripts/mint_key.py --rotate mei@example.com
    ../.venv/bin/python ../scripts/mint_key.py --revoke mei@example.com
    ../.venv/bin/python ../scripts/mint_key.py --list
    ../.venv/bin/python ../scripts/mint_key.py --seed-demo     # raj, mei, zed, admin

A key is printed ONCE and only its hash is stored (state/users.json), so a
lost key is rotated, never recovered. --seed-demo also writes the four demo
keys to state/demo_keys.txt so you can paste them into the UI; that file is
plaintext, mode 0600, gitignored, and read by nothing but you.
"""
import argparse
import os
import pathlib
import sys

STAGE2 = pathlib.Path(__file__).resolve().parent.parent / "stage2"
sys.path.insert(0, str(STAGE2))
os.chdir(STAGE2)

from ami import auth          # noqa: E402


def issue(store, email, name, role):
    """Create the account, or rotate the key if it already has one."""
    if store.find(email):
        return store.find(email), store.rotate(email)
    return store.create(email, name, role)


def seed_demo(store):
    lines = ["# demo keys — plaintext, gitignored. Re-running --seed-demo replaces them."]
    for email, name, role in auth.DEMO_USERS:
        principal, key = issue(store, email, name, role)
        lines.append(f"{email}\t{key}")
        print(f"  {email:<20} {principal.role:<6} user_id={principal.user_id}")
    out = store.path.parent / "demo_keys.txt"
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write("\n".join(lines) + "\n")
    print(f"keys written to {out}")


def main(argv=None, store=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--create", metavar="EMAIL")
    g.add_argument("--rotate", metavar="EMAIL")
    g.add_argument("--revoke", metavar="EMAIL")
    g.add_argument("--list", action="store_true")
    g.add_argument("--seed-demo", action="store_true")
    p.add_argument("--name", default="")
    p.add_argument("--admin", action="store_true")
    a = p.parse_args(argv)
    store = store or auth.UserStore()

    try:
        if a.create:
            principal, key = store.create(a.create, a.name or a.create,
                                          "admin" if a.admin else "user")
            print(f"created {principal.email}  user_id={principal.user_id}")
            print(f"key (shown once, store it now): {key}")
        elif a.rotate:
            print(f"new key for {a.rotate} (shown once; the old key and its "
                  f"sessions are dead): {store.rotate(a.rotate)}")
        elif a.revoke:
            store.revoke(a.revoke)
            print(f"revoked {a.revoke}")
        elif a.list:
            for u in store.listing():
                state = "REVOKED" if u["revoked_at"] else "active"
                print(f"{u['user_id']}  {u['email']:<22} {u['role']:<6} {state}")
        else:
            seed_demo(store)
    except (ValueError, KeyError) as e:
        sys.exit(f"error: {e.args[0]}")


if __name__ == "__main__":
    main()
