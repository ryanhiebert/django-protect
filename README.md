# django-protect
A new take on security modeling for Django

## Installation

```bash
pip install django-protect
```

## Usage

```python
from django_protect import auth

def look_ma_no_args():
    print(f'Hello, {auth.user().username}!')

with auth.use(User.objects.get(username='admin')):
    look_ma_no_args()  # No need to pass the user around!
```

## Impersonation

```python
from django_protect import auth

def see_who_i_really_am():
    if auth.impersonator():
        print(f"I am {auth.impersonator().username}, pretending to be {auth.user().username}!")
    else:
        print(f"I am {auth.user().username}!")

with auth.use(
    User.objects.get(username='standard'),
    impersonator=User.objects.get(username='admin'),
):
    see_who_i_really_am()
```

## Django Session Impersonation

Because impersonation is considered at the foundation of this package,
it includes utilities for handling impersonation in the Django session.
Be careful, these are dangerous operations!
Be sure that you only allow appropriate users to use these functions.

```python
from django.contrib.auth import login, get_user_model
from django_protect import impersonate, unimpersonate

def myview(request):
    login(request, get_user_model().objects.get(username="impersonator"))
    # The current session must be logged in before impersonating

    impersonate(request, get_user_model().objects.get(username="user"))
    # Now the current user is the impersonated user.
    # New requests will also see this impersonation.

    get_impersonator(request)  # See who started the impersonation

    unimpersonate(request)
    # The original session has been restored,
    # and the impersonator is the user again.
```
