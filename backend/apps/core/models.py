import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Base class adding created_at / updated_at to every model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """Base class for models that should expose a UUID (not sequential int)
    identifier externally — used for anything referenced in public URLs or
    third-party integrations (e.g. Agent.public_widget_id-style usage)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantOwnedModel(TimeStampedModel):
    """Base class for every model that belongs to a single Business.

    Every subclass gets a mandatory, indexed `business` FK. Combined with
    `TenantScopedQuerySetMixin` / `TenantScopedViewSet` in
    apps.core.permissions, this is the backbone of tenant isolation:
    no query against a TenantOwnedModel should ever be issued without a
    business filter derived from the authenticated request context, never
    from a client-supplied value.
    """

    business = models.ForeignKey(
        "tenants.Business",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
    )

    class Meta:
        abstract = True
