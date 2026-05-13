"""Client serializers."""

from rest_framework import serializers

from apps.clients.models import Client


class ClientSerializer(serializers.ModelSerializer):
    firm_id = serializers.UUIDField(read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True)

    class Meta:
        model = Client
        fields = ("id", "name", "email", "firm_id", "firm_name", "created_at")
        read_only_fields = fields
