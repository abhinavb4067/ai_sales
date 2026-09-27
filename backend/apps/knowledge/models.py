from django.db import models

from apps.core.models import TenantOwnedModel


class KnowledgeDocument(TenantOwnedModel):
    """A unit of business knowledge. `agent` is nullable: null means
    business-wide knowledge shared by every agent on the tenant; set means
    knowledge private to that one agent (Refinement 5 — business-level vs
    agent-specific scope). Retrieval always filters by business AND
    (agent IS NULL OR agent = <current agent>), enforced in
    apps.knowledge.services so one agent can never surface another
    agent's private knowledge.
    """

    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual entry"
        FAQ = "faq", "FAQ"
        PDF = "pdf", "PDF"
        TXT = "txt", "Text file"
        DOCX = "docx", "Word document"
        CSV = "csv", "CSV"
        URL = "url", "Website URL"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    agent = models.ForeignKey(
        "agents.Agent", on_delete=models.CASCADE, related_name="knowledge_documents",
        null=True, blank=True,
        help_text="Null = shared across all agents in this business.",
    )
    source_type = models.CharField(max_length=16, choices=SourceType.choices, default=SourceType.MANUAL)
    title = models.CharField(max_length=255)
    # Phase 1: raw text entered directly (manual/FAQ). Phase 2+: populated
    # by the document-processing pipeline after extracting from file/url.
    content = models.TextField(blank=True)
    file = models.FileField(upload_to="knowledge_documents/", null=True, blank=True)
    source_url = models.URLField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.TextField(blank=True)

    class Meta:
        db_table = "knowledge_document"
        indexes = [models.Index(fields=["business", "agent", "status"])]

    def __str__(self):
        return self.title


class KnowledgeChunk(TenantOwnedModel):
    """A retrievable slice of a KnowledgeDocument. `business` and `agent`
    are denormalized from the parent document specifically so retrieval
    queries never need to join across tenants — defense in depth for
    tenant isolation, not just a performance shortcut."""

    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    agent = models.ForeignKey(
        "agents.Agent", on_delete=models.CASCADE, related_name="knowledge_chunks", null=True, blank=True
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    # Populated once embedding generation is wired up (Phase 2). Null in
    # Phase 1 — MySQLKeywordRetriever doesn't need it.
    embedding = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_chunk"
        indexes = [models.Index(fields=["business", "agent"])]
        ordering = ["chunk_index"]
