from django.conf import settings


DEFAULT_SITE = getattr(settings, "JSONRPC_DEFAULT_SITE", None)
