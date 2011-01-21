from django.conf.urls.defaults import *
from django.conf import settings
from jsonrpc.site import default_site


import jsonrpc.tests.methods


urlpatterns = patterns('',
    (r'^json/browse/', "jsonrpc.views.browse", {}, "jsonrpc_browser"),
    (r'^json/(?P<method>[a-zA-Z0-9.]+)$', default_site.dispatch),
    (r'^json/', default_site.dispatch, {}, "jsonrpc_mountpoint"),
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
