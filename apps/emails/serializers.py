"""Email thread + message serializers. Encryption is handled transparently by the field."""

from rest_framework import serializers

from apps.emails.models import EmailMessage, EmailThread


class EmailMessageSerializer(serializers.ModelSerializer):
    body = serializers.CharField(source="encrypted_body", read_only=True)

    class Meta:
        model = EmailMessage
        fields = (
            "id",
            "thread_id",
            "sender_email",
            "recipients",
            "body",
            "sent_at",
            "external_message_id",
        )
        read_only_fields = fields


class EmailThreadListSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="encrypted_subject", read_only=True)
    message_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = EmailThread
        fields = (
            "id",
            "client_id",
            "subject",
            "external_thread_id",
            "first_message_at",
            "last_message_at",
            "message_count",
        )
        read_only_fields = fields


class EmailThreadDetailSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="encrypted_subject", read_only=True)
    messages = EmailMessageSerializer(many=True, read_only=True)

    class Meta:
        model = EmailThread
        fields = (
            "id",
            "client_id",
            "firm_id",
            "subject",
            "external_thread_id",
            "first_message_at",
            "last_message_at",
            "up_to_message_at",
            "messages",
        )
        read_only_fields = fields
