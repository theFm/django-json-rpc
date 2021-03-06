import uuid
from django.test.client import Client
from jsonrpc._json import loads, dumps
from jsonrpc.types import Any, Object


class JsonRpcTestClient(Client):
    def store_exc_info(self, **kwargs):
        # Do not store view exceptions. Let the site object handle them.
        pass


class TestServiceProxy(object):
    def __init__(self, service_url, service_name=None, version='1.0'):
        self.__version = str(version)
        self.__service_url = service_url
        self.__service_name = service_name
        self.client = JsonRpcTestClient()

    def __getattr__(self, name):
        if self.__service_name != None:
            name = "%s.%s" % (self.__service_name, name)
        return TestServiceProxy(self.__service_url, name, self.__version)

    def __call__(self, *args, **kwargs):
        params = kwargs if len(kwargs) else args
        if Any.kind(params) == Object and self.__version != '2.0':
            raise ValueError('Unsupported arg type for JSON-RPC 1.0 ' \
                             '(the default version for this client, ' \
                             'pass version="2.0" to use keyword arguments)')
        response = self.client.post(self.__service_url, dumps({
                                "jsonrpc": self.__version,
                                "method": self.__service_name,
                                'params': params,
                                'id': str(uuid.uuid1()),
        }), content_type="application/json-rpc")
        y = loads(response.content)
        if y.get("error", None):
            try:
                from django.conf import settings
                if settings.DEBUG:
                    print '%s error %r' % (self.__service_name, y)
            except:
                pass
        return y