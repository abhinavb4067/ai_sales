from django.contrib import admin

from apps.conversations.models import Conversation, Message, MessageAttachment

admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(MessageAttachment)
