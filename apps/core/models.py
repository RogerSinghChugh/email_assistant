"""Shared abstract base models."""

import uuid

from django.db import models


class TimeStampedUUIDModel(models.Model):
    """UUID primary key + created_at / updated_at audit columns."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
