"""Sessions: a key buys a short-lived token, and the token dies when it should."""

import pytest

from ami import auth


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def sessions(users, clock):
    return auth.SessionManager(users.store, idle=60, absolute=600, clock=clock)


class TestLogin:

    def test_valid_key_gets_a_token_and_the_principal(self, users, sessions):
        token, principal = sessions.login(users.keys["raj"])
        assert principal == users.principals["raj"]
        assert sessions.resolve(token) == principal

    @pytest.mark.parametrize("bad", [None, "", "ami_nope", "not-a-key", 5])
    def test_bad_key_gets_nothing(self, sessions, bad):
        assert sessions.login(bad) is None

    def test_each_login_is_a_new_token(self, users, sessions):
        a, _ = sessions.login(users.keys["raj"])
        b, _ = sessions.login(users.keys["raj"])
        assert a != b

    def test_token_does_not_contain_the_key_or_the_user(self, users, sessions):
        token, principal = sessions.login(users.keys["raj"])
        assert users.keys["raj"] not in token and principal.user_id not in token

    def test_the_key_is_not_a_token(self, users, sessions):
        sessions.login(users.keys["raj"])
        assert sessions.resolve(users.keys["raj"]) is None

    def test_a_user_id_is_not_a_token(self, users, sessions):
        sessions.login(users.keys["raj"])
        assert sessions.resolve(users.principals["raj"].user_id) is None

    def test_tokens_are_held_only_as_hashes(self, users, sessions):
        token, _ = sessions.login(users.keys["raj"])
        assert token not in sessions._sessions


class TestResolve:

    @pytest.mark.parametrize("bad", [None, "", "nope", 5, "x" * 500])
    def test_junk_tokens_resolve_to_nobody(self, sessions, bad):
        assert sessions.resolve(bad) is None

    def test_tokens_of_two_users_stay_apart(self, users, sessions):
        t_raj, _ = sessions.login(users.keys["raj"])
        t_mei, _ = sessions.login(users.keys["mei"])
        assert sessions.resolve(t_raj).email == "raj@example.com"
        assert sessions.resolve(t_mei).email == "mei@example.com"

    def test_idle_timeout(self, users, sessions, clock):
        token, _ = sessions.login(users.keys["raj"])
        clock.advance(61)
        assert sessions.resolve(token) is None

    def test_activity_keeps_a_session_alive_only_until_the_absolute_limit(self, users, sessions, clock):
        token, _ = sessions.login(users.keys["raj"])
        for _ in range(10):                      # touched every 59s: never idle
            clock.advance(59)
            assert sessions.resolve(token)       # ...up to t=590s
        clock.advance(5)
        assert sessions.resolve(token)           # t=595s, still inside 600s
        clock.advance(6)                         # t=601s, active 6s ago: only age can end it
        assert sessions.resolve(token) is None

    def test_an_expired_token_stays_dead(self, users, sessions, clock):
        token, _ = sessions.login(users.keys["raj"])
        clock.advance(61)
        sessions.resolve(token)
        clock.now = 1000.0                       # even if the clock were wound back
        assert sessions.resolve(token) is None


class TestEndingASession:

    def test_logout(self, users, sessions):
        token, _ = sessions.login(users.keys["raj"])
        sessions.logout(token)
        assert sessions.resolve(token) is None

    def test_logout_of_junk_is_harmless(self, sessions):
        sessions.logout(None)
        sessions.logout("nope")

    def test_revoking_the_account_ends_live_sessions(self, users, sessions):
        token, _ = sessions.login(users.keys["mei"])
        users.store.revoke("mei@example.com")
        assert sessions.resolve(token) is None

    def test_rotating_the_key_ends_sessions_opened_with_the_old_one(self, users, sessions):
        old_token, _ = sessions.login(users.keys["mei"])
        new_key = users.store.rotate("mei@example.com")
        assert sessions.resolve(old_token) is None
        new_token, _ = sessions.login(new_key)                 # the new key works
        assert sessions.resolve(new_token).email == "mei@example.com"

    def test_other_users_sessions_survive(self, users, sessions):
        t_raj, _ = sessions.login(users.keys["raj"])
        users.store.revoke("mei@example.com")
        assert sessions.resolve(t_raj)

    def test_expired_sessions_are_swept_on_login(self, users, sessions, clock):
        for _ in range(5):
            sessions.login(users.keys["raj"])
        clock.advance(700)
        sessions.login(users.keys["raj"])
        assert len(sessions._sessions) == 1
