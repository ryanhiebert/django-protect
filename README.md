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
