"""Summary read serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.summaries.models import EmailSummary


class SummaryReadSerializer(serializers.ModelSerializer):
    """The encrypted_payload field decrypts transparently on read."""

    payload = serializers.JSONField(source="encrypted_payload", read_only=True)
    is_stale = serializers.SerializerMethodField()

    class Meta:
        model = EmailSummary
        fields = (
            "id",
            "thread_id",
            "firm_id",
            "payload",
            "emails_analyzed",
            "last_refreshed_at",
            "up_to_message_at",
            "is_stale",
        )
        read_only_fields = fields

    def get_is_stale(self, obj: EmailSummary) -> bool:
        """True if new messages have arrived since the summary was generated."""
        from apps.emails.models import (
            EmailMessage,
        )  # local import — avoid app-init cycle

        if obj.up_to_message_at is None:
            return True
        latest = (
            EmailMessage.objects.filter(thread_id=obj.thread_id)
            .order_by("-sent_at")
            .values_list("sent_at", flat=True)
            .first()
        )
        if latest is None:
            return False
        return latest > obj.up_to_message_at


class TaskStatusSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(allow_null=True)
    error = serializers.CharField(allow_null=True, required=False)
