from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from apps.core.fields import EncryptedTextField
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
        API = "api", "External REST API"
        DATABASE = "database", "External Database (read-only)"

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
    # Only for source_type=api: {"headers": {...}}. Deliberately no secret
    # credential storage here yet — only non-secret headers (e.g. a
    # public API's "Accept" header). An API requiring a secret key should
    # not be wired up through this field until a proper encrypted
    # credential path exists (see apps.integrations for the pattern).
    source_config = models.JSONField(default=dict, blank=True)
    # Only for source_type=database: encrypted JSON {"dialect", "host",
    # "port", "database", "user", "password", "table"}. A dedicated
    # field (not source_config) specifically so a DB password is never
    # stored in plaintext JSON the way api headers are — see
    # apps.core.fields.EncryptedTextField. The business is responsible
    # for the credential actually being read-only; the app only
    # enforces the query shape (see apps.knowledge.db_source).
    external_db_credentials = EncryptedTextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.TextField(blank=True)
    # SHA-256 of the last successfully extracted content — lets scheduled
    # re-sync (apps.knowledge.tasks.resync_external_sources) skip
    # re-chunking/re-embedding when a URL/API source's content hasn't
    # actually changed since the last crawl.
    content_checksum = models.CharField(max_length=64, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

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
    # Populated once embedding generation is wired up (Phase 2). Null
    # when no embedding provider is configured — KeywordRetriever (see
    # apps.knowledge.retrieval) doesn't need it. Kept as JSONField (not
    # Postgres-specific) so the in-process cosine-similarity retriever
    # keeps working identically on every backend.
    embedding = models.JSONField(null=True, blank=True)
    # Native Postgres vector column (requires the pgvector extension —
    # see scripts/setup_postgres.sql) used by PgVectorRetriever for a
    # real ANN/cosine query instead of a Python-side loop. Populated
    # alongside `embedding` whenever the active DB backend is Postgres;
    # left null on other backends (e.g. the sqlite test database), where
    # PgVectorRetriever is simply never selected (see get_retriever()).
    embedding_vector = VectorField(dimensions=settings.EMBEDDING_VECTOR_DIMENSIONS, null=True, blank=True)

    class Meta:
        db_table = "knowledge_chunk"
        indexes = [models.Index(fields=["business", "agent"])]
        ordering = ["chunk_index"]
