from base import JsonRpcTestCase, TransactionJsonRpcTestCase


class SimpleTests(JsonRpcTestCase):
    def test_simple(self):
        self.assertEqual(1 + 1, 2)
