from rest_framework.routers import DefaultRouter

from apps.leads.views import LeadStageViewSet, LeadViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("lead-stages", LeadStageViewSet, basename="lead-stage")

urlpatterns = router.urls
