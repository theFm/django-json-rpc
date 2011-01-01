from django.conf.urls.defaults import *
from django.conf import settings
from jsonrpc import jsonrpc_site


urlpatterns = patterns('',
    (r'^json/(?P<method>[a-zA-Z0-9.]+)$', jsonrpc_site.dispatch),
    (r'^json/', jsonrpc_site.dispatch, {}, "jsonrpc_mountpoint"),
)


if settings.DEBUG:
    from django.views.static import serve
    _media_url = settings.MEDIA_URL
    if _media_url.startswith('/'):
        _media_url = _media_url[1:]
        urlpatterns += patterns('',
                                (r'^%s(?P<path>.*)$' % _media_url,
                                serve,
                                {'document_root': settings.MEDIA_ROOT}))
    del(_media_url, serve)
