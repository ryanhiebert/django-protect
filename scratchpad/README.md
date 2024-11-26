# django-protect
A new take on security modeling for Django

For now, I'm just collecting my thoughts and API ideas here.

## Globals

Globals are scary, and rightly so. They leak details.
But a well-placed global can be a powerful tool.

The request is not a global in Django, but it is in Flask.
I think that Django got this right.
Ditto for the session.
Business logic should not be digging into the request object.

On principle, I think many people would also say that models
should be separate from business logic.
While this can be true at large scale,
I have never worked on a project where our team was best served
by separating models from business logic.
If we had, we would have ended up creating our own pseudo-ORM
based on some plugin architecture for the models as a database layer.
Instead, we were better served by viewing the ORM as a business logic toolkit.

This is a practical distinction.
What things should be decoupled from each other isn't a principle,
but as you make these trade-offs over and over some patterns emerge.
As projects start, it's very difficult to see exactly
what the optimal boundaries are.
When you start, you shouldn't decouple any more than is necessary.
Then you start seeing places that you can benefit from decoupling.
HTTP is often decoupled before the database,
and the database is decoupled far before you need
even further decouple from the ORM.

This makes sense of viewing the ORM as a business logic toolkit.
It's often farther down the road, if at all,
that a project is likely to benefit from decoupling the ORM.

It's also a quite difficult job to write an expressive layer
that decouples the database access layer.
Database access typically requires a lot of hooks to customize
how the database is accessed.
If you don't access the database correctly,
you can quickly and easily make something that performs poorly.

Databases are the ultimate shared state, and the super-global.
It then makes sense that APIs for database access might be the
optimal place to make careful, more extensive use of globals.

This is the starting point for this document and this project.
We can do more to help the ORM protect our database access,
particularly around securing database access.

But the scope goes even farther.
When we manage security, it is about our whole application,
from the business layer (often in the ORM)
all the way to the HTTP layer where we figure out who the user is.

By using a well-placed global, we can make it simpler to enforce
global security policies across our application and into our database.

## Authentication

We oddly use the `request` object as a pseudo-global in Django.
As I mentioned above, I think that the request shouldn't be a global.
However, the user is almost always a critical piece of data
at every layer of our application.

```python
from django_protect import authn

with authn.use(User.objects.get(username='admin')):
    # Now, we can go deep into functions without passing the user around
    user = authn.get()

user = authn.get()  # Will throw an error if we forgot to set the user!
```

### Authorization

Here's a key insight: the authentication user
and the authorization user
are not necessarily the same!

So while you *could* just use the `authn` user to enforce authorization,
you can also decouple the two and enable a way to impersonate users
without compromising the knowledge of who is actually authenticated.

```python
from django_protect import authz

with (
    authn.use(User.objects.get(username='admin')),
    authz.use(User.objects.get(username='standard')),
):
    # Now we perform the action as a standard user
    ProtectedModel.objects.filter(users_with_access=authz.get())
    # But we can do audits that know who *actually* did it!
    AuditLog.objects.create(user=authn.get(), for_user=authz.get(), text="viewed ProtectedModel")
```

### Tenancy

I haven't quite figured out whether to do tenancy in this package,
or to leave it as a separate one.
Many projects I do need tenancy,
but tenancy is very much an afterthought to Django right now.

If I integrated tenancy as well,
it might look like:

```python
from django_protect import tenant

with tenant.use(Tenant.objects.get(name='acme')):
    # Now we can access the tenant without passing it around
    tenant.get()
```

### Automatic QuerySet filtering

This is where things can get really powerful.
We can protect our model access automatically!

```python
from django_protect import authz

class MyModelManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(users_with_access=authz.get())

    def unrestricted(self):
        return super().get_queryset()

class MyModel(models.Model):
    users_with_access = models.ManyToManyField(User)
    objects = MyModelManager()
```

Now, whenever you query the model, it will *by default* filter
to the instances the user has access to.
There's still an escape hatch to get everything,
but you have to explicitly ask for it,
so that this dangerous operation is more obvious.

### Scope invalidation

`authz` implies that `authn` is already set.
If it changes, `authz` should be invalidated.
Likely the same is true for `tenant`,
and would make sense for other customer-specific globals as well.
Need to encode dependencies between globals,
so that when a parent changes,
the children can immediately be invalid.

```python
from django_protect import authn, authz

with authn.use(User.objects.get(username='admin')):
    with authz.use(User.objects.get(username='standard')):
        with authn.use(User.objects.get(username='another')):
            # Throws an error because authz was invalidated but not reset!
            ProtectedModel.objects.filter(users_with_access=authz.get())
```

### Non-contextual configuration

It should be possible to configure the global state in a place
where using a context manager isn't reasonable.

TODO: Think this one through. Can we avoid this API?
I'd rather rely exclusively on context managers if we can help it.

```python
from django_protect import authn

authn.set(User.objects.get(username='admin'))
# Do some stuff
authn.reset()
```

NOTE: If this API is implemented, setting the state this way
      should also invalidate dependent scope.


### Permissions

Permissions always have a scope.
This is something that Django's permissions got wrong by default,
because it's permissions are global.
Furthermore, permissions can cause cascading permissions.

TODO: instance permissions vs class permissions vs parent instance permissions
Are model class permissions just parent permissions in disguise?
Is there an implied global "instance" that works at similar scope to Django?
I'm not sure, so for now we'll prefer instance permissions.

```python
class MyModelManager(models.Manager):
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    def get_permission_annotations(self) -> dict[str, Expression]:
        return {
            'view': F('users_with_access').contains(authz.get()),
            'edit': F('users_with_access').contains(authz.get()),
            'delete': F('users_with_access').contains(authz.get()),
        }

    def get_queryset(self):
        # TODO: Probably should also prefix these annotations
        return self.get_queryset().annotate(self.get_permission_annotations())

    def unrestricted(self):
        return self.get_queryset()


class MyModel(models.Model):
    users_with_access = models.ManyToManyField(User)
    objects = MyModelManager()
    permissions = Permissions()  # A descriptor
```

#### Auto-create value annotation

Partcularly, how can we automatically assign a tenant or owner to a model?
