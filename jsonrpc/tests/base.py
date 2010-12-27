from django.test import TestCase, TransactionTestCase
from django.test.client import Client


class JsonRpcTestMixin(object):
    def _pre_setup(self):
        self.client = Client()
        super(JsonRpcTestMixin, self)._pre_setup()


class JsonRpcTestCase(TestCase, JsonRpcTestMixin):
    pass


class TransactionJsonRpcTestCase(TransactionTestCase, JsonRpcTestMixin):
    pass
