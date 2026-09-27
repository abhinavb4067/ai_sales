from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class Conversation(TenantOwnedModel):
    class Channel(models.TextChoices):
        PLAYGROUND = "playground", "Playground"
        WEBSITE = "website", "Website Widget"
        API = "api", "Public API"
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"
        SLACK = "slack", "Slack"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WAITING = "waiting", "Waiting"
        RESOLVED = "resolved", "Resolved"
        HUMAN_HANDOFF = "human_handoff", "Human Handoff"

    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.PLAYGROUND)
    external_customer_ref = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Set for playground conversations — the staff user testing the agent.",
    )
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_conversation"
        indexes = [models.Index(fields=["business", "agent", "status"])]

    def __str__(self):
        return f"Conversation {self.id} ({self.agent_id})"


class Message(TenantOwnedModel):
    class SenderType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        AI = "ai", "AI"
        AGENT_USER = "agent_user", "Staff"
        SYSTEM = "system", "System"

    class ContentType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"
        AUDIO = "audio", "Audio"
        FILE = "file", "File"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=16, choices=SenderType.choices)
    content_type = models.CharField(max_length=16, choices=ContentType.choices, default=ContentType.TEXT)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    tool_calls = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "conversations_message"
        indexes = [models.Index(fields=["conversation", "created_at"])]
        ordering = ["created_at"]


class MessageAttachment(TenantOwnedModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="message_attachments/")
    content_type = models.CharField(max_length=128, blank=True)
    size = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "conversations_message_attachment"
