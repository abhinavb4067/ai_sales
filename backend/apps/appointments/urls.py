from rest_framework.routers import DefaultRouter

from apps.appointments.views import AppointmentViewSet, FollowUpViewSet

router = DefaultRouter()
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("follow-ups", FollowUpViewSet, basename="follow-up")

urlpatterns = router.urls
