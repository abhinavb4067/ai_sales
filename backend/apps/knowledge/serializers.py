import json

from rest_framework import serializers

from apps.knowledge.db_source import SUPPORTED_DIALECTS
from apps.knowledge.models import KnowledgeDocument

TEXT_SOURCE_TYPES = {KnowledgeDocument.SourceType.MANUAL, KnowledgeDocument.SourceType.FAQ}
FILE_SOURCE_TYPES = {
    KnowledgeDocument.SourceType.PDF,
    KnowledgeDocument.SourceType.DOCX,
    KnowledgeDocument.SourceType.TXT,
    KnowledgeDocument.SourceType.CSV,
}

MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15MB — matches the platform-wide upload limit
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "txt": {"text/plain"},
    "csv": {"text/csv", "application/vnd.ms-excel"},
}
REQUIRED_DB_CREDENTIAL_KEYS = {"dialect", "host", "database", "user", "password", "table"}

# Magic-byte signatures — the client-reported Content-Type header
# (checked below) is trivially spoofable, so this is the real check that
# an uploaded file actually is what its source_type claims. TXT/CSV have
# no reliable magic bytes and are intentionally not checked here — their
# risk is already bounded by size limit + being parsed as plain text,
# never executed.
FILE_SIGNATURES = {
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),  # docx is a zip container
}


def _has_valid_signature(file_obj, source_type: str) -> bool:
    signatures = FILE_SIGNATURES.get(source_type)
    if not signatures:
        return True
    file_obj.seek(0)
    header = file_obj.read(8)
    file_obj.seek(0)
    return any(header.startswith(sig) for sig in signatures)


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    # Write-only — mirrors apps.integrations.serializers.IntegrationSerializer's
    # pattern for secrets: accepted as a plain dict on input, stored
    # encrypted via KnowledgeDocument.external_db_credentials, never
    # returned in any response.
    database_credentials = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id", "agent", "source_type", "title", "content", "file", "source_url", "source_config",
            "database_credentials", "status", "failure_reason", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "failure_reason", "created_at", "updated_at"]

    def validate_agent(self, value):
        request = self.context["request"]
        if value is not None and value.business_id != request.business.id:
            raise serializers.ValidationError("Invalid agent.")
        return value

    def validate_file(self, value):
        if value is None:
            return value
        if value.size > MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError("File exceeds the 15MB upload limit.")
        return value

    def validate(self, attrs):
        source_type = attrs.get("source_type", KnowledgeDocument.SourceType.MANUAL)

        if source_type in TEXT_SOURCE_TYPES:
            if not attrs.get("content", "").strip():
                raise serializers.ValidationError({"content": "This field may not be blank."})
        elif source_type in FILE_SOURCE_TYPES:
            file_obj = attrs.get("file")
            if not file_obj:
                raise serializers.ValidationError({"file": "A file is required for this source type."})
            allowed_types = ALLOWED_UPLOAD_CONTENT_TYPES.get(source_type, set())
            if allowed_types and getattr(file_obj, "content_type", None) not in allowed_types:
                raise serializers.ValidationError(
                    {"file": f"Expected a {source_type} file but got {getattr(file_obj, 'content_type', 'unknown')}."}
                )
            if not _has_valid_signature(file_obj, source_type):
                raise serializers.ValidationError(
                    {"file": f"File content does not match the expected {source_type} format."}
                )
        elif source_type in (KnowledgeDocument.SourceType.URL, KnowledgeDocument.SourceType.API):
            if not attrs.get("source_url", "").strip():
                raise serializers.ValidationError({"source_url": "This field may not be blank."})
            config = attrs.get("source_config") or {}
            if not isinstance(config, dict):
                raise serializers.ValidationError({"source_config": "Must be an object."})
            if source_type == KnowledgeDocument.SourceType.API:
                headers = config.get("headers", {})
                if not isinstance(headers, dict) or not all(isinstance(v, str) for v in headers.values()):
                    raise serializers.ValidationError({"source_config": "headers must be a flat object of strings."})
            if source_type == KnowledgeDocument.SourceType.URL and "max_pages" in config:
                max_pages = config.get("max_pages")
                if not isinstance(max_pages, int) or not 1 <= max_pages <= 50:
                    raise serializers.ValidationError({"source_config": "max_pages must be an integer between 1 and 50."})
        elif source_type == KnowledgeDocument.SourceType.DATABASE:
            credentials = attrs.get("database_credentials")
            if not credentials and not self.instance:
                raise serializers.ValidationError({"database_credentials": "This field is required for database sources."})
            if credentials:
                missing = REQUIRED_DB_CREDENTIAL_KEYS - credentials.keys()
                if missing:
                    raise serializers.ValidationError({"database_credentials": f"Missing required keys: {missing}."})
                if credentials.get("dialect") not in SUPPORTED_DIALECTS:
                    raise serializers.ValidationError(
                        {"database_credentials": f"dialect must be one of {SUPPORTED_DIALECTS}."}
                    )
        else:
            raise serializers.ValidationError({"source_type": "Unsupported source type."})

        return attrs

    def create(self, validated_data):
        credentials = validated_data.pop("database_credentials", None)
        if credentials is not None:
            validated_data["external_db_credentials"] = json.dumps(credentials)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        credentials = validated_data.pop("database_credentials", None)
        if credentials is not None:
            validated_data["external_db_credentials"] = json.dumps(credentials)
        return super().update(instance, validated_data)
