"""Healthcheck view."""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthcheckView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes: list = []

    @extend_schema(
        responses={
            200: inline_serializer(
                name="Health", fields={"status": serializers.CharField()}
            ),
        }
    )
    def get(self, request):
        return Response({"status": "ok"})
