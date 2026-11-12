"""Request correlation without recording request bodies, URLs or secrets."""
import logging
import traceback
import uuid
from contextvars import ContextVar
from . import settings

_request_id = ContextVar('request_id', default='-')
logger = logging.getLogger('nohentai.api')


def bind_request():
    request_id = uuid.uuid4().hex
    return request_id, _request_id.set(request_id)


def reset_request(marker):
    _request_id.reset(marker)


def log_failure(operation, exc):
    frames = traceback.extract_tb(exc.__traceback__)
    own = next((f for f in reversed(frames) if f.filename.startswith(str(settings.ROOT / 'backend'))), None)
    location = f'{own.filename.rsplit("/", 1)[-1]}:{own.lineno}' if own else '-'
    # Exception messages and arguments may contain provider URLs or API keys.
    logger.error('request_id=%s operation=%s error=%s location=%s',
                 _request_id.get(), operation, type(exc).__name__, location)
