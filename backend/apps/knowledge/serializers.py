from rest_framework import serializers

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


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = [
            "id", "agent", "source_type", "title", "content", "file", "source_url",
            "status", "failure_reason", "created_at", "updated_at",
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
        elif source_type == KnowledgeDocument.SourceType.URL:
            if not attrs.get("source_url", "").strip():
                raise serializers.ValidationError({"source_url": "This field may not be blank."})
        else:
            raise serializers.ValidationError({"source_type": "Unsupported source type."})

        return attrs
