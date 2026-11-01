from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import business_overview
from apps.core.permissions import IsBusinessMember


class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        days = max(1, min(days, 365))
        return Response(business_overview(request.business, days=days))
