from rest_framework import permissions, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin
from apps.knowledge.models import KnowledgeDocument
from apps.knowledge.serializers import KnowledgeDocumentSerializer, FILE_SOURCE_TYPES, TEXT_SOURCE_TYPES
from apps.knowledge.services import create_pending_document, ingest_manual_text


class KnowledgeDocumentViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    queryset = KnowledgeDocument.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        validated = serializer.validated_data
        source_type = validated.get("source_type", KnowledgeDocument.SourceType.MANUAL)

        if source_type in TEXT_SOURCE_TYPES:
            document = ingest_manual_text(
                business=self.request.business,
                agent=validated.get("agent"),
                title=validated["title"],
                content=validated["content"],
                source_type=source_type,
            )
        else:
            # PDF/DOCX/TXT/CSV/URL: create the row immediately, process
            # asynchronously — the HTTP request doesn't wait on extraction/
            # chunking/embedding.
            document = create_pending_document(
                business=self.request.business,
                agent=validated.get("agent"),
                title=validated["title"],
                source_type=source_type,
                file=validated.get("file"),
                source_url=validated.get("source_url", ""),
            )
            from apps.knowledge.tasks import process_document_task

            process_document_task.delay(document.id)

        serializer.instance = document
