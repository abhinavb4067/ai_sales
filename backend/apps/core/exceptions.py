from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class APIError(APIException):
    """Raise with a machine-readable code + human message for consistent
    error payloads across the whole API. Subclasses DRF's APIException so
    it's caught by the normal DRF exception-handling pipeline instead of
    bubbling up as an unhandled 500."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(detail=message, code=code)


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        return None

    code = getattr(exc, "code", None) or response.status_text.upper().replace(" ", "_")
    detail = response.data

    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
    else:
        message = detail

    response.data = {
        "success": False,
        "error": {
            "code": code,
            "message": message if isinstance(message, str) else "Request failed.",
            "details": detail if not isinstance(message, str) or message != detail else None,
        },
    }
    return response
