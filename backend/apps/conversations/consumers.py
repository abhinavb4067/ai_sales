from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


@database_sync_to_async
def _resolve_business_for_ws_user(user, requested_business_id):
    """WebSocket equivalent of apps.core.permissions.resolve_business_for_request
    — never trusts a client-supplied business id except to narrow which of
    *the user's own* active memberships it means."""
    if not user or not user.is_authenticated:
        return None

    memberships = user.memberships.select_related("business").filter(status="active")
    if requested_business_id:
        membership = memberships.filter(business_id=requested_business_id).first()
        return membership.business if membership else None

    membership = memberships.first()
    return membership.business if membership else None


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    """One group per business — every staff dashboard connection for a
    business joins the same group and receives every conversation/message/
    lead/handoff event for that tenant. Scoped entirely server-side from
    the authenticated user's membership, same rule as every REST endpoint:
    never trust a client-supplied business id for authorization.
    """

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode()
        requested_business_id = parse_qs(query_string).get("business_id", [None])[0]
        business = await _resolve_business_for_ws_user(self.scope.get("user"), requested_business_id)

        if business is None:
            await self.close(code=4401)
            return

        self.group_name = f"business_{business.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Consumers here are push-only — the dashboard drives state changes
    # through REST, not through the socket, so incoming client frames are
    # ignored rather than acted on.
    async def receive_json(self, content, **kwargs):
        pass

    async def conversation_event(self, event):
        await self.send_json(event["payload"])
