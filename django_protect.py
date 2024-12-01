from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial
from importlib import import_module

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.auth import SESSION_KEY
from django.contrib.auth import get_user_model
from django.contrib.auth import load_backend
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.middleware import auser
from django.contrib.auth.middleware import get_user
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.utils.crypto import constant_time_compare
from django.utils.functional import SimpleLazyObject

__all__ = ["auth", "impersonate", "unimpersonate", "get_impersonator"]


@dataclass
class _AuthContext:
    user: AbstractBaseUser | AnonymousUser
    impersonator: AbstractBaseUser | AnonymousUser | None


class _Auth:
    def __init__(self):
        self.__context = ContextVar[_AuthContext]("Auth__var")

    def user(self) -> AbstractBaseUser | AnonymousUser:
        return self.__context.get().user

    def impersonator(self) -> AbstractBaseUser | None:
        return self.__context.get().impersonator

    @contextmanager
    def use(
        self,
        user: AbstractBaseUser | AnonymousUser,
        impersonator: AbstractBaseUser | None = None,
    ) -> Iterator[None]:
        token = self.__context.set(_AuthContext(user, impersonator))
        try:
            yield
        finally:
            self.__context.reset(token)

    # I've intentionally avoided adding a ``set`` method to avoid
    # changes without a context manager. I suspect this may change.


auth = _Auth()


IMPERSONATOR_SESSION_KEY = "_protect_impersonator_user_id"
IMPERSONATOR_BACKEND_SESSION_KEY = "_protect_impersonator_backend"
IMPERSONATOR_HASH_SESSION_KEY = "_protect_impersonator_hash"
IMPERSONATOR_SESSION_SESSION_KEY = "_protect_impersonator_session"


def get_impersonator(request: HttpRequest) -> AbstractBaseUser | None:
    """
    Return the user model instance for the impersonator in the session.
    If there's no impersonator, return None.
    """
    # This is mostly a copy of the get_user function from auth,
    # except that it uses the impersonator versions of the session keys
    # and it errors if there is an impersonator in the session
    # but we couldn't validate it.

    try:
        user_id = get_user_model()._meta.pk.to_python(
            request.session[IMPERSONATOR_SESSION_KEY]
        )
        backend_path = request.session[IMPERSONATOR_BACKEND_SESSION_KEY]
    except KeyError:
        return None
    else:
        if backend_path in settings.AUTHENTICATION_BACKENDS:
            backend = load_backend(backend_path)
            user = backend.get_user(user_id)
            # Verify the session
            if hasattr(user, "get_session_auth_hash"):
                session_hash = request.session.get(IMPERSONATOR_HASH_SESSION_KEY)
                if not session_hash:  # pragma: no cover
                    session_hash_verified = False
                else:
                    session_auth_hash = user.get_session_auth_hash()
                    session_hash_verified = constant_time_compare(
                        session_hash, session_auth_hash
                    )
                if not session_hash_verified:  # pragma: no cover
                    raise ImpersonationError("Impersonator found but invalid.")
            else:
                pass  # pragma: no cover
            return user
    raise ImpersonationError("Impersonator found but invalid.")  # pragma: no cover


class ImpersonationError(Exception):
    """An error during an impersonation operation."""


def _load_user_session(request: HttpRequest, session_key: str | None, /):
    """Do what the session and auth middlewares do."""

    # Do what the SessionMiddleware does to load a session.
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(session_key)

    # Do what the auth middleware does to load the user.
    request.user = SimpleLazyObject(lambda: get_user(request))
    request.auser = partial(auser, request)


def impersonate(request: HttpRequest, user: AbstractBaseUser, backend=None) -> None:
    """
    Start a new session impersonating the given user.

    The current user and session are retained to inspect and restore.
    """
    if IMPERSONATOR_SESSION_KEY in request.session:
        raise ImpersonationError("End impersonation before impersonating.")
    if SESSION_KEY not in request.session:
        raise ImpersonationError("Cannot impersonate without an existing user session.")

    impersonator = request.session[SESSION_KEY]
    impersonator_backend = request.session[BACKEND_SESSION_KEY]
    impersonator_hash = request.session[HASH_SESSION_KEY]
    impersonator_session_key = request.session._session_key
    # Should we match the expiration of the new session to the original?

    request.session.save()  # Save the current session to restore
    _load_user_session(request, None)
    login(request, user, backend=backend)

    # Save the original user and session for later inspection and restoration.
    request.session[IMPERSONATOR_SESSION_KEY] = impersonator
    request.session[IMPERSONATOR_BACKEND_SESSION_KEY] = impersonator_backend
    request.session[IMPERSONATOR_HASH_SESSION_KEY] = impersonator_hash
    request.session[IMPERSONATOR_SESSION_SESSION_KEY] = impersonator_session_key


def unimpersonate(request: HttpRequest) -> None:
    """
    End the current session and restore the original impersonator's session.

    The impersonator is retained as the current user on the request object.
    """
    if IMPERSONATOR_SESSION_SESSION_KEY not in request.session:
        raise ImpersonationError("Not impersonating.")

    impersonator_session_key = request.session[IMPERSONATOR_SESSION_SESSION_KEY]
    logout(request)
    _load_user_session(request, impersonator_session_key)
