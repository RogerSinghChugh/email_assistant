"""Auth serializers."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Accountant


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Embed firm_id and role into the JWT so AuthZ can read them without a DB hit."""

    @classmethod
    def get_token(cls, user: Accountant):
        token = super().get_token(user)
        token["firm_id"] = str(user.firm_id) if user.firm_id else None
        token["role"] = user.role
        return token


class MeSerializer(serializers.ModelSerializer):
    firm_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Accountant
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "firm_id",
            "created_at",
        )
        read_only_fields = fields
