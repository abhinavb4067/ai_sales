from rest_framework.routers import DefaultRouter

from apps.knowledge.views import KnowledgeDocumentViewSet

router = DefaultRouter()
router.register("knowledge", KnowledgeDocumentViewSet, basename="knowledge-document")

urlpatterns = router.urls
