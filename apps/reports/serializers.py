"""Report row serializers — aggregate row + nested drillable summary list."""

from rest_framework import serializers


class SummaryEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    thread_id = serializers.UUIDField()
    thread_subject = serializers.CharField()
    emails_analyzed = serializers.IntegerField()
    last_refreshed_at = serializers.DateTimeField()
    up_to_message_at = serializers.DateTimeField(allow_null=True)


class GlobalSummaryEntrySerializer(SummaryEntrySerializer):
    client_id = serializers.UUIDField()
    client_name = serializers.CharField()


class FirmClientReportRowSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    client_name = serializers.CharField()
    client_email = serializers.EmailField()
    summary_count = serializers.IntegerField()
    total_emails_analyzed = serializers.IntegerField()
    last_summarized = serializers.DateTimeField()
    summaries = SummaryEntrySerializer(many=True)


class GlobalFirmReportRowSerializer(serializers.Serializer):
    firm_id = serializers.UUIDField()
    firm_name = serializers.CharField()
    summary_count = serializers.IntegerField()
    client_count = serializers.IntegerField()
    total_emails_analyzed = serializers.IntegerField()
    last_summarized = serializers.DateTimeField()
    summaries = GlobalSummaryEntrySerializer(many=True)
