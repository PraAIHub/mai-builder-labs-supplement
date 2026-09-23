"""Identity: keys authenticate, hashes are all we keep, and revoking is real."""

import json
import re
import stat
import sys

import pytest

from ami import auth

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))
import mint_key  # noqa: E402


class TestAuthenticate:

    def test_valid_key_yields_that_user(self, users):
        p = users.store.authenticate(users.keys["raj"])
        assert p == users.principals["raj"]
        assert (p.email, p.role) == ("raj@example.com", "user")

    def test_each_key_maps_to_its_own_user(self, users):
        ids = {who: users.store.authenticate(k).user_id for who, k in users.keys.items()}
        assert len(set(ids.values())) == len(users.keys)

    @pytest.mark.parametrize("bad", [None, "", "ami_", "ami_nope", "raj@example.com",
                                     123, "x" * 500, "ami_" + "x" * 500])
    def test_bad_credentials_are_none_not_errors(self, users, bad):
        assert users.store.authenticate(bad) is None

    def test_a_key_is_not_a_user_id(self, users):
        # The credential must be the only way in: an id, an email, or a hash
        # of a key must not authenticate.
        rec = json.loads(users.store.path.read_text())[users.principals["raj"].user_id]
        for attempt in (users.principals["raj"].user_id, "raj@example.com",
                        "ami_" + rec["key_hash"]):
            assert users.store.authenticate(attempt) is None


class TestOpaqueId:

    def test_user_id_is_not_the_email(self, users):
        p = users.principals["raj"]
        assert p.user_id != p.email and "@" not in p.user_id
        assert re.fullmatch(r"[0-9a-f]{32}", p.user_id)

    def test_email_is_normalised(self, users):
        assert users.store.find("  RAJ@Example.com ") == users.principals["raj"]

    def test_duplicate_active_email_rejected(self, users):
        with pytest.raises(ValueError, match="already has an active account"):
            users.store.create("Raj@example.com", "Impostor")

    def test_bad_email_and_role_rejected(self, users):
        with pytest.raises(ValueError):
            users.store.create("not-an-email", "x")
        with pytest.raises(ValueError):
            users.store.create("new@example.com", "x", role="root")


class TestNothingSecretAtRest:

    def test_file_holds_hashes_never_keys(self, users):
        text = users.store.path.read_text()
        for key in users.keys.values():
            assert key not in text
        assert auth.KEY_PREFIX not in text
        assert all(len(r["key_hash"]) == 64 for r in json.loads(text).values())

    def test_file_is_owner_only(self, users, tmp_path):
        probe = tmp_path / "probe"
        probe.write_text("x")
        probe.chmod(0o600)
        if stat.S_IMODE(probe.stat().st_mode) != 0o600:
            pytest.skip("filesystem does not honour POSIX modes (e.g. /mnt/c on WSL)")
        assert stat.S_IMODE(users.store.path.stat().st_mode) == 0o600

    def test_corrupt_file_fails_closed(self, users):
        users.store.path.write_text("{not json")
        with pytest.raises(json.JSONDecodeError):
            auth.UserStore(users.store.path)             # never "no users, carry on"


class TestRotateAndRevoke:

    def test_rotate_kills_old_key_keeps_identity(self, users):
        old = users.keys["mei"]
        new = users.store.rotate("mei@example.com")
        assert users.store.authenticate(old) is None
        p = users.store.authenticate(new)
        assert p.user_id == users.principals["mei"].user_id
        assert p.epoch == users.principals["mei"].epoch + 1     # old sessions detectable

    def test_revoke_kills_key_and_get(self, users):
        users.store.revoke("mei@example.com")
        assert users.store.authenticate(users.keys["mei"]) is None
        assert users.store.get(users.principals["mei"].user_id) is None

    def test_reissue_after_revoke_is_a_new_person(self, users):
        # An address can be reassigned; the new holder must not inherit the
        # old holder's id, and so not their data or history.
        users.store.revoke("mei@example.com")
        p, _ = users.store.create("mei@example.com", "Someone Else")
        assert p.user_id != users.principals["mei"].user_id

    def test_unknown_account_errors(self, users):
        with pytest.raises(KeyError):
            users.store.rotate("ghost@example.com")
        with pytest.raises(KeyError):
            users.store.revoke("ghost@example.com")

    def test_revoke_reaches_a_running_server(self, users):
        """The CLI is a different process from the server: a revoke written
        by one must be seen by a UserStore that was already open."""
        running = auth.UserStore(users.store.path)
        assert running.authenticate(users.keys["raj"])
        auth.UserStore(users.store.path).revoke("raj@example.com")   # "the CLI"
        assert running.authenticate(users.keys["raj"]) is None


    def test_rotate_reaches_a_running_server_even_back_to_back(self, users):
        """A rotate rewrites the same number of bytes. Written straight after
        another save it can share its timestamp — the running store must
        still see it, or the old key's sessions outlive the rotation."""
        running = auth.UserStore(users.store.path)
        for _ in range(20):
            other = auth.UserStore(users.store.path)
            new_key = other.rotate("raj@example.com")
            assert running.authenticate(new_key), "the running store missed a rotate"
            assert running.get(users.principals["raj"].user_id).epoch == other.find("raj@example.com").epoch


class TestPersistence:

    def test_survives_reload(self, users):
        again = auth.UserStore(users.store.path)
        assert again.authenticate(users.keys["admin"]).is_admin

    def test_listing_never_includes_secrets(self, users):
        rows = users.store.listing()
        assert len(rows) == len(auth.DEMO_USERS)
        assert all("key_hash" not in r for r in rows)


class TestMintKeyCli:

    def test_seed_demo_issues_four_working_keys(self, users, tmp_state, capsys):
        store = auth.UserStore(tmp_state / "state" / "cli_users.json")
        mint_key.main(["--seed-demo"], store=store)
        lines = (tmp_state / "state" / "demo_keys.txt").read_text().splitlines()
        keys = dict(l.split("\t") for l in lines if not l.startswith("#"))
        assert set(keys) == {e for e, _, _ in auth.DEMO_USERS}
        assert all(store.authenticate(k) for k in keys.values())

    def test_reseed_replaces_keys(self, tmp_state):
        store = auth.UserStore(tmp_state / "state" / "cli_users.json")
        mint_key.main(["--seed-demo"], store=store)
        first = (tmp_state / "state" / "demo_keys.txt").read_text()
        mint_key.main(["--seed-demo"], store=store)
        assert (tmp_state / "state" / "demo_keys.txt").read_text() != first
        assert len(store.listing()) == len(auth.DEMO_USERS)      # rotated, not duplicated

    def test_create_prints_key_once(self, tmp_state, capsys):
        store = auth.UserStore(tmp_state / "state" / "cli_users.json")
        mint_key.main(["--create", "new@example.com", "--name", "New"], store=store)
        key = re.search(r"ami_\S+", capsys.readouterr().out).group(0)
        assert store.authenticate(key).email == "new@example.com"
        mint_key.main(["--list"], store=store)
        assert key not in capsys.readouterr().out

    def test_duplicate_create_exits_nonzero(self, users):
        with pytest.raises(SystemExit):
            mint_key.main(["--create", "raj@example.com"], store=users.store)
