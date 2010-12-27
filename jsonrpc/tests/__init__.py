from django.test import TestCase
from jsonrpc import jsonrpc_method
from jsonrpc.proxy import TestServiceProxy


@jsonrpc_method("echo(message=String) -> String")
def echo(request, message):
    return message


class SimpleTests(TestCase):
    def setUp(self):
        self.proxy = TestServiceProxy("/json/")

    def test_simple(self):
        response = self.proxy.echo(u"test")
        self.assertEqual(response["error"], None)
        self.assertEqual(response["result"], u"test")
