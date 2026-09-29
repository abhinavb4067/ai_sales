from django.urls import path

from apps.conversations.consumers import ConversationConsumer

websocket_urlpatterns = [
    path("ws/conversations/", ConversationConsumer.as_asgi()),
]
