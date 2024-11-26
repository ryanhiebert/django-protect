from collections.abc import Iterator
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser


@dataclass
class _AuthContext:
    user: AbstractBaseUser | AnonymousUser
    impersonator: AbstractBaseUser | AnonymousUser | None


class _Auth:
    def __init__(self):
        self.__context = ContextVar[_AuthContext]("Auth__var")

    def user(self) -> AbstractBaseUser | AnonymousUser:
        return self.__context.get().user

    def impersonator(self) -> AbstractBaseUser | AnonymousUser | None:
        return self.__context.get().impersonator

    @contextmanager
    def use(
        self,
        user: AbstractBaseUser | AnonymousUser,
        impersonator: AbstractBaseUser | AnonymousUser | None = None,
    ) -> Iterator[None]:
        token = self.__context.set(_AuthContext(user, impersonator))
        try:
            yield
        finally:
            self.__context.reset(token)


auth = _Auth()
