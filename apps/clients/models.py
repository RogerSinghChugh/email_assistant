"""Client model — the external entities CPA firms serve."""

from django.db import models

from apps.core.models import TimeStampedUUIDModel


class Client(TimeStampedUUIDModel):
    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="clients",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["firm"]),
            models.Index(fields=["firm", "email"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"
