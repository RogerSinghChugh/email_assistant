"""Firm + Accountant (AUTH_USER_MODEL)."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import AccountantManager


class Firm(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class RoleChoices(models.TextChoices):
    MEMBER = "member", "Member"
    ADMIN = "admin", "Admin"
    SUPERUSER = "superuser", "Superuser"


class Accountant(AbstractUser):
    """Custom user model. Auth by email. Firm-scoped except for role=superuser."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Override username — we auth by email only.
    username = None
    email = models.EmailField(unique=True)

    firm = models.ForeignKey(
        Firm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accountants",
    )
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.MEMBER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = AccountantManager()

    class Meta:
        ordering = ("email",)
        indexes = [
            models.Index(fields=["firm"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def is_firm_admin(self) -> bool:
        return self.role == RoleChoices.ADMIN

    @property
    def is_role_superuser(self) -> bool:
        return self.role == RoleChoices.SUPERUSER or self.is_superuser
