from rest_framework.routers import DefaultRouter

from apps.agents.views import AgentToolViewSet, AgentViewSet

router = DefaultRouter()
router.register("agents", AgentViewSet, basename="agent")
router.register(r"agents/(?P<agent_pk>[^/.]+)/tools", AgentToolViewSet, basename="agent-tool")

urlpatterns = router.urls
