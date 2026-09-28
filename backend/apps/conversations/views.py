from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.models import Agent
from apps.ai.orchestrator import receive_message
from apps.apikeys.authentication import ApiKeyAuthentication
from apps.apikeys.models import UsageEvent
from apps.apikeys.permissions import HasApiKey
from apps.apikeys.throttling import ApiKeyRateThrottle, WidgetRateThrottle
from apps.billing.services import enforce_subscription_and_limits
from apps.conversations.models import Conversation, Message
from apps.conversations.serializers import (
    ConversationDetailSerializer,
    ConversationSerializer,
    PlaygroundChatRequestSerializer,
    PublicChatRequestSerializer,
    WidgetChatRequestSerializer,
)
from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin


class ConversationListView(TenantScopedQuerySetMixin, generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Conversation.objects.all().select_related("agent").order_by("-last_activity_at")

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ConversationDetailView(TenantScopedQuerySetMixin, generics.RetrieveAPIView):
    serializer_class = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Conversation.objects.all().prefetch_related("messages")


class ConversationTakeoverView(APIView):
    """A staff member claims a HUMAN_HANDOFF conversation. Phase 2 keeps
    this to "who owns it" — actually disabling/limiting the AI on taken-over
    conversations (AI_DISABLED / AI_SUGGEST_ONLY modes from the
    architecture) is deferred; assignment alone is enough for a human to
    start responding through the dashboard/API in this phase."""

    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, business=request.business)
        conversation.assigned_to = request.user
        conversation.save(update_fields=["assigned_to", "updated_at"])
        return Response(ConversationSerializer(conversation).data)


class ConversationResolveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, business=request.business)
        conversation.status = Conversation.Status.RESOLVED
        conversation.save(update_fields=["status", "updated_at"])
        return Response(ConversationSerializer(conversation).data)


def _conversation_history_for_prompt(conversation, exclude_message_id=None) -> list[dict]:
    role_map = {
        Message.SenderType.CUSTOMER: "user",
        Message.SenderType.AI: "assistant",
        Message.SenderType.AGENT_USER: "assistant",
    }
    history = []
    qs = conversation.messages.exclude(sender_type=Message.SenderType.SYSTEM).order_by("created_at")
    if exclude_message_id:
        qs = qs.exclude(id=exclude_message_id)
    for msg in qs:
        role = role_map.get(msg.sender_type)
        if role:
            history.append({"role": role, "content": msg.content})
    return history


def _run_chat(*, business, agent, conversation, message, api_key=None):
    """Shared chat pipeline for every channel (playground, public API,
    website widget). Only the auth/permission front door and how the
    Conversation is looked up/created differ between channels — the actual
    orchestrator call, message persistence, and usage logging must stay
    identical everywhere so all channels behave the same way.
    """
    enforce_subscription_and_limits(business)

    history = _conversation_history_for_prompt(conversation)

    Message.objects.create(
        business=business,
        conversation=conversation,
        sender_type=Message.SenderType.CUSTOMER,
        content=message,
    )

    result = receive_message(
        agent=agent,
        conversation=conversation,
        history=history,
        customer_message=message,
    )

    ai_message = Message.objects.create(
        business=business,
        conversation=conversation,
        sender_type=Message.SenderType.AI,
        content=result.content,
        metadata={
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "knowledge_chunks_used": result.knowledge_chunks_used,
        },
        tool_calls=[
            {"tool_name": r.tool_name, "status": r.status, "result": r.result}
            for r in result.tool_results
        ]
        or None,
    )

    conversation.last_activity_at = ai_message.created_at
    conversation.save(update_fields=["last_activity_at"])

    UsageEvent.objects.create(
        business=business,
        agent=agent,
        api_key=api_key,
        channel=conversation.channel,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    return Response(
        {
            "success": True,
            "conversation_id": conversation.id,
            "message": {
                "id": ai_message.id,
                "content": ai_message.content,
                "tool_calls": ai_message.tool_calls,
                "created_at": ai_message.created_at,
            },
            "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
            "conversation_status": conversation.status,
            "escalated": result.escalated,
        },
        status=status.HTTP_200_OK,
    )


class PlaygroundChatView(APIView):
    """Business-owner-facing "test my agent" endpoint. Uses the exact same
    apps.ai.orchestrator.receive_message() pipeline that production
    channels (widget/API) use — no parallel simplified chat implementation.
    """

    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    throttle_scope = "playground"

    def post(self, request):
        serializer = PlaygroundChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agent = get_object_or_404(Agent, pk=data["agent_id"], business=request.business)

        conversation_id = data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(
                Conversation, pk=conversation_id, business=request.business, agent=agent
            )
        else:
            conversation = Conversation.objects.create(
                business=request.business,
                agent=agent,
                channel=Conversation.Channel.PLAYGROUND,
                started_by=request.user,
            )

        return _run_chat(business=request.business, agent=agent, conversation=conversation, message=data["message"])


class PublicChatView(APIView):
    """Server-to-server Chat API for external integrations — authenticated
    with a business-issued ApiKey (Authorization: Bearer sk_live_...),
    never a dashboard JWT. request.business comes from the key, never from
    the request body.
    """

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKey]
    throttle_classes = [ApiKeyRateThrottle]
    throttle_scope = "public_api"

    def post(self, request):
        serializer = PublicChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agent = get_object_or_404(
            Agent, pk=data["agent_id"], business=request.business, status=Agent.Status.ACTIVE
        )

        conversation_id = data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(
                Conversation, pk=conversation_id, business=request.business, agent=agent
            )
        else:
            conversation = Conversation.objects.create(
                business=request.business,
                agent=agent,
                channel=Conversation.Channel.API,
                external_customer_ref=data.get("customer_ref", ""),
            )

        return _run_chat(
            business=request.business,
            agent=agent,
            conversation=conversation,
            message=data["message"],
            api_key=request.api_key,
        )


class WidgetConfigView(APIView):
    """Public, unauthenticated — public_widget_id is a non-secret
    identifier safe to embed in a <script> tag on a customer's website.
    Only returns display config, never anything sensitive."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, widget_id):
        agent = get_object_or_404(Agent, public_widget_id=widget_id, status=Agent.Status.ACTIVE)
        return Response(
            {
                "agent_name": agent.name,
                "greeting": agent.greeting,
                "tone": agent.tone,
                "language": agent.language,
            }
        )


class WidgetChatView(APIView):
    """Public website widget chat endpoint. No secret to authenticate with
    (the widget runs in a customer's browser, where anything embedded is
    inherently visible) — abuse is bounded with a looser IP-based throttle
    instead, same tradeoff every embeddable chat widget makes."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [WidgetRateThrottle]
    throttle_scope = "widget"

    def post(self, request, widget_id):
        agent = get_object_or_404(Agent, public_widget_id=widget_id, status=Agent.Status.ACTIVE)
        business = agent.business

        serializer = WidgetChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conversation_id = data.get("conversation_id")
        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, business=business, agent=agent)
        else:
            conversation = Conversation.objects.create(
                business=business,
                agent=agent,
                channel=Conversation.Channel.WEBSITE,
                external_customer_ref=data.get("session_id", ""),
            )

        return _run_chat(business=business, agent=agent, conversation=conversation, message=data["message"])
