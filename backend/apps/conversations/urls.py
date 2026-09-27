from django.urls import path

from apps.conversations.views import (
    ConversationDetailView,
    ConversationListView,
    ConversationResolveView,
    ConversationTakeoverView,
    PlaygroundChatView,
    PublicChatView,
    WidgetChatView,
    WidgetConfigView,
)

urlpatterns = [
    path("conversations/", ConversationListView.as_view(), name="conversation-list"),
    path("conversations/<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<int:pk>/takeover/", ConversationTakeoverView.as_view(), name="conversation-takeover"),
    path("conversations/<int:pk>/resolve/", ConversationResolveView.as_view(), name="conversation-resolve"),
    path("playground/chat/", PlaygroundChatView.as_view(), name="playground-chat"),
    path("public/chat/", PublicChatView.as_view(), name="public-chat"),
    path("widget/<uuid:widget_id>/config/", WidgetConfigView.as_view(), name="widget-config"),
    path("widget/<uuid:widget_id>/chat/", WidgetChatView.as_view(), name="widget-chat"),
]
