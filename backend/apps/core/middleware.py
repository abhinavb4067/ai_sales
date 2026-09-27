import uuid

from django.http import HttpResponse


class RequestContextMiddleware:
    """Attaches a request_id to every request for log correlation.

    Tenant resolution (business_id) is deliberately NOT done here — it
    requires JWT/API-key authentication which DRF performs at the view
    layer, after Django middleware runs. See apps.core.permissions for
    where request.business is actually resolved and enforced.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class WidgetCorsMiddleware:
    """The website widget (apps.conversations.views.WidgetConfigView /
    WidgetChatView) is embedded on arbitrary customer domains we can't
    know in advance — the opposite of every other endpoint, which is only
    ever called from our own dashboard origin (see CORS_ALLOWED_ORIGINS).
    Rather than opening CORS_ALLOW_ALL_ORIGINS globally, only these two
    public/unauthenticated widget paths get a wildcard origin; everything
    else keeps going through corsheaders' normal allow-list.
    """

    WIDGET_PATH_PREFIX = "/api/v1/widget/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.WIDGET_PATH_PREFIX):
            if request.method == "OPTIONS":
                response = HttpResponse(status=204)
            else:
                response = self.get_response(request)
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type"
            return response
        return self.get_response(request)
