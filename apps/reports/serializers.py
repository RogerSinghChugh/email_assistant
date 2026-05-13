"""Report row serializers (plain dict rows)."""

from rest_framework import serializers


class FirmClientReportRowSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(source="thread__client_id")
    client_name = serializers.CharField(source="thread__client__name")
    client_email = serializers.EmailField(source="thread__client__email")
    summary_count = serializers.IntegerField()
    total_emails_analyzed = serializers.IntegerField()
    last_summarized = serializers.DateTimeField()


class GlobalFirmReportRowSerializer(serializers.Serializer):
    firm_id = serializers.UUIDField()
    firm_name = serializers.CharField(source="firm__name")
    summary_count = serializers.IntegerField()
    client_count = serializers.IntegerField()
    total_emails_analyzed = serializers.IntegerField()
    last_summarized = serializers.DateTimeField()
