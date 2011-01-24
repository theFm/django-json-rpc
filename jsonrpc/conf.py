from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from jsonrpc import app_settings
from jsonrpc.site import JsonRpcSite


def setup_default_site():
    site_class = app_settings.DEFAULT_SITE
    if site_class is None:
        return JsonRpcSite("jsonrpc")
    if isinstance(site_class, (str, unicode)):
        module_name, class_name = site_class.rsplit('.', 1)
        try:
            site_class = getattr(import_module(module_name), class_name)
        except ImportError:
            raise ImproperlyConfigured("Can't import site `%s` from " \
                                       "`%s`" % (class_name, module_name))
    elif callable(site_class):
        site_class = site_class()
    else:
        raise ImproperlyConfigured("JSONRPC_DEFAULT_SITE must be a callable " \
                                   "that returns a JSON-RPC site instance " \
                                   "or an import path string pointing to a " \
                                   "class.")
    return site_class("jsonrpc")
default_site = setup_default_site()
