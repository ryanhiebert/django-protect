from contextlib import ExitStack
from contextlib import contextmanager
from contextvars import ContextVar
from contextvars import Token
from dataclasses import dataclass
from typing import Callable
from typing import Iterator
from typing import overload

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser

# class __Authn:
#     def __init__(self):
#         self.__subscribers = ContextVar[list[Callable[[Token], Callable[[Token], None]]]](
#             "authn__subscribers", default=[]
#         )
#         self.__var = ContextVar[AbstractBaseUser | AnonymousUser]("authn__var")

#     @contextmanager
#     def use(self, user: AbstractBaseUser | AnonymousUser, /):
#         token = self.__var.set(user)
#         try:
#             reset_subscribers = []
#             for fn in self.__subscribers.get():
#                 reset_subscribers.append(fn(token))
#             yield
#             for fn in filter(None, reset_subscribers):
#                 fn(token)
#         finally:
#             self.__var.reset(token)

#     def get(self) -> AbstractBaseUser | AnonymousUser:
#         return self.__var.get()

#     def subscribe(
#         self, fn: Callable[[Token], Callable[[Token], None]], /
#     ) -> Callable[[], None]:
#         self.__subscribers.get().append(fn)
#         return lambda: self.__subscribers.get().remove(fn)


# authn = __Authn()


# class __Authz:
#     def __init__(self):
#         self.__var = ContextVar[AbstractBaseUser | AnonymousUser]("authz_var")
#         self.__valid = ContextVar[bool]("authz_valid")
#         self.__unsubscribe = authn.subscribe(self.__authn_set)

#     def __del__(self):
#         self.__unsubscribe()

#     def __authn_set(self, _: Token, /):
#         valid_token = self.__valid.set(False)
#         return lambda _: self.__valid.reset(valid_token)

#     @contextmanager
#     def use(self, user: AbstractBaseUser | AnonymousUser, /, impersonate: bool = False):
#         with ExitStack() as stack:
#             if not impersonate:
#                 stack.enter_context(authn.use(user))
#             token = self.__var.set(user)
#             try:
#                 yield
#             finally:
#                 self.__var.reset(token)

#     def get(self) -> AbstractBaseUser | AnonymousUser:
#         # Get the value from the context first to give the LookupError if unset.
#         value = self.__var.get()
#         if not self.__valid.get():
#             raise RuntimeError("authn value has changed.")
#         return value


# authz = __Authz()


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

    @overload
    def __use(self, user: AbstractBaseUser | AnonymousUser, /): ...
    @overload
    def __use(
        self,
        user: AbstractBaseUser | AnonymousUser,
        /,
        impersonator: AbstractBaseUser | AnonymousUser,
    ): ...
    def __use(self, user, /, impersonator=None) -> Iterator[None]:
        token = self.__context.set(_AuthContext(user, impersonator))
        try:
            yield
        finally:
            self.__context.reset(token)

    use = contextmanager(__use)


auth = _Auth()
