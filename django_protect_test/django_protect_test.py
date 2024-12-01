import pytest
from django.contrib.auth import login
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse

from django_protect import ImpersonationError
from django_protect import auth
from django_protect import get_impersonator
from django_protect import impersonate
from django_protect import unimpersonate


class TestAuth:
    def test_use(self):
        anonymous, user = AnonymousUser(), User()
        with pytest.raises(LookupError):
            auth.user()
        with auth.use(user):
            assert auth.user() == user
            with auth.use(anonymous):
                assert auth.user() == anonymous
            assert auth.user() == user
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


class TestImpersonation:
    @pytest.mark.django_db
    def test_impersonate_unauthenticated(self, rf):
        """Should error when there is no logged in user."""

        @SessionMiddleware
        @AuthenticationMiddleware
        def view(request):
            impersonate(request, User.objects.create(username="user"))

        with pytest.raises(ImpersonationError):
            view(rf.post("/"))

    @pytest.mark.django_db
    def test_impersonate(self, rf):
        """Should impersonate a user."""

        @SessionMiddleware
        @AuthenticationMiddleware
        def view(request):
            login(request, User.objects.create(username="user"))
            assert get_impersonator(request) is None
            assert request.user.username == "user"
            impersonate(request, User.objects.create(username="another"))
            assert get_impersonator(request).username == "user"
            assert request.user.username == "another"
            return HttpResponse()

        view(rf.post("/"))

    @pytest.mark.django_db
    def test_impersonate_already_impersonating(self, rf):
        """Should error when already impersonating."""

        @SessionMiddleware
        @AuthenticationMiddleware
        def view(request):
            login(request, User.objects.create(username="user"))
            impersonate(request, User.objects.create(username="another"))
            impersonate(request, User.objects.create(username="yetanother"))

        with pytest.raises(ImpersonationError):
            view(rf.post("/"))

    @pytest.mark.django_db
    def test_unimpersonate_not_impersonating(self, rf):
        """Should error when not impersonating."""

        @SessionMiddleware
        @AuthenticationMiddleware
        def view(request):
            login(request, User.objects.create(username="user"))
            unimpersonate(request)

        with pytest.raises(ImpersonationError):
            view(rf.post("/"))

    @pytest.mark.django_db
    def test_unimpersonate(self, rf):
        """Should unimpersonate a user."""

        @SessionMiddleware
        @AuthenticationMiddleware
        def view(request):
            login(request, User.objects.create(username="user"))
            assert request.user.username == "user"
            impersonate(request, User.objects.create(username="anotheruser"))
            unimpersonate(request)
            assert request.user.username == "user"
            return HttpResponse()

        view(rf.post("/"))
