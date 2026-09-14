"""§7.2 error code contract."""

from fastapi import Request
from fastapi.responses import JSONResponse

# code -> (http_status, retryable)
ERROR_TABLE: dict[str, tuple[int, bool]] = {
    "INVALID_URL": (400, False),
    "VIDEO_TOO_LONG": (400, False),
    "VIDEO_UNAVAILABLE": (404, False),
    "AGE_RESTRICTED": (403, False),
    "GEO_BLOCKED": (403, False),
    "LIVE_STREAM_UNSUPPORTED": (400, False),
    "DRM_PROTECTED": (403, False),
    "EXTRACTION_FAILED": (502, True),
    "RATE_LIMITED": (429, True),
    "QUEUE_FULL": (503, True),
    "DOWNLOAD_TEMPORARILY_DISABLED": (503, True),
    "GPU_OOM": (500, True),
    "NOT_FOUND": (404, False),
    "FILE_TOO_LARGE": (400, False),
    "UNSUPPORTED_FORMAT": (400, False),
    "VALIDATION_ERROR": (400, False),
    "EMAIL_TAKEN": (409, False),
    "INVALID_CREDENTIALS": (401, False),
    "NOT_AUTHENTICATED": (401, False),
    "PENDING_APPROVAL": (403, False),
    "FORBIDDEN": (403, False),
}


class ApiError(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None):
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.status_code, self.retryable = ERROR_TABLE.get(code, (500, False))
        super().__init__(message)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "retryable": exc.retryable,
            }
        },
    )
