from channels.testing import WebsocketCommunicator
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.agents.models import Agent
from apps.conversations.consumers import ConversationConsumer
from apps.conversations.ws_auth import JWTAuthMiddleware
from apps.core.testing import create_business_with_owner
from apps.leads.models import LeadStage
from apps.leads.services import change_stage, get_or_create_lead_for_conversation


def _make_app():
    return JWTAuthMiddleware(ConversationConsumer.as_asgi())


class LeadRealtimeTests(TestCase):
    async def test_lead_created_and_stage_changed_are_broadcast(self):
        from asgiref.sync import sync_to_async

        user, business = await sync_to_async(create_business_with_owner)()
        agent = await sync_to_async(Agent.objects.create)(business=business, name="Agent")

        token = str(AccessToken.for_user(user))
        communicator = WebsocketCommunicator(_make_app(), f"/ws/conversations/?token={token}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        def _create_lead_and_change_stage():
            from apps.conversations.models import Conversation

            conversation = Conversation.objects.create(business=business, agent=agent)
            lead = get_or_create_lead_for_conversation(business=business, agent=agent, conversation=conversation)
            new_stage = LeadStage.objects.filter(business=business).order_by("order")[1]
            change_stage(lead, new_stage)
            return lead

        lead = await sync_to_async(_create_lead_and_change_stage)()

        created_event = await communicator.receive_json_from()
        self.assertEqual(created_event["event"], "lead.created")
        self.assertEqual(created_event["lead"]["id"], lead.id)

        stage_event = await communicator.receive_json_from()
        self.assertEqual(stage_event["event"], "lead.stage_changed")
        self.assertEqual(stage_event["lead"]["id"], lead.id)

        await communicator.disconnect()
