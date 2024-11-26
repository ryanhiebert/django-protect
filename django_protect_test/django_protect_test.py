import pytest

from django_protect import auth
from django.contrib.auth.models import AnonymousUser, User


class TestAuth:
    def test_use(self):
        anonymous, user = AnonymousUser(), User()
        with pytest.raises(LookupError):
            auth.user()
        with auth.use(anonymous):
            assert auth.user() == anonymous
            with auth.use(user):
                assert auth.user() == user
            assert auth.user() == anonymous
        with pytest.raises(LookupError):
            auth.user()

    def test_use_impersonator(self):
        anonymous, user = AnonymousUser(), User()
        with pytest.raises(LookupError):
            auth.user()
        with pytest.raises(LookupError):
            auth.impersonator()
        with auth.use(anonymous, impersonator=user):
            assert auth.user() == anonymous
            assert auth.impersonator() == user
            with auth.use(user):
                assert auth.user() == user
                assert auth.impersonator() is None
            assert auth.user() == anonymous
            assert auth.impersonator() == user
        with pytest.raises(LookupError):
            auth.user()
        with pytest.raises(LookupError):
            auth.impersonator()
