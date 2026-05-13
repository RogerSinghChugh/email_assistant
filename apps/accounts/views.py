"""Auth views — /me. Token obtain/refresh use simplejwt's default views with our serializer."""

from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.serializers import MeSerializer


class MeView(RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
