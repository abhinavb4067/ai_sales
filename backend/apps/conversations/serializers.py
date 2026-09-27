from rest_framework import serializers

from apps.conversations.models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "sender_type", "content_type", "content", "metadata", "tool_calls", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "agent", "channel", "status", "external_customer_ref", "last_activity_at", "created_at"]
        read_only_fields = ["id", "last_activity_at", "created_at"]


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]


class PlaygroundChatRequestSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(max_length=4000, allow_blank=False)


class PublicChatRequestSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(max_length=4000, allow_blank=False)
    customer_ref = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class WidgetChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(max_length=4000, allow_blank=False)
    session_id = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
