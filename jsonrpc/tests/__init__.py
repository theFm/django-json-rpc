import unittest
import urllib
from django.test import TestCase
from django.utils import simplejson as json
from django.contrib.auth.models import User
from jsonrpc import jsonrpc_method, Any, SortedDict
from jsonrpc.exceptions import InvalidParamsError, InvalidCredentialsError
from jsonrpc.proxy import TestServiceProxy, JsonRpcTestClient
from jsonrpc import RpcMethod
from jsonrpc.site import validate_params
from jsonrpc.types import String, Object, Array, Nil, Number


# Register JSON-RPC methods
import jsonrpc.tests.methods


class RpcMethodClassTestCase(unittest.TestCase):
    def setUp(self):
        def no_arg_method():
            return None
        def add_method(request, param1, param2):
            return param1 + param2
        self.no_arg_method = no_arg_method
        self.add_method = add_method

    def test_rpc_method_signature_extraction(self):
        rpc_method = RpcMethod(self.add_method)
        self.assertEqual(RpcMethod.parse_signature(self.no_arg_method, ""), {"method_name": "no_arg_method", "arguments": SortedDict(), "return_type": Any})
        self.assertEqual(RpcMethod.parse_signature(self.no_arg_method, "rpc_method"), {"method_name": "rpc_method", "arguments": SortedDict(), "return_type": Any})
        self.assertEqual(RpcMethod.parse_signature(self.no_arg_method, "namespace.rpc_method"), {"method_name": "namespace.rpc_method", "arguments": SortedDict(), "return_type": Any})
        self.assertEqual(RpcMethod.parse_signature(self.no_arg_method, "namespace.rpc_method() -> Number"), {"method_name": "namespace.rpc_method", "arguments": SortedDict(), "return_type": Number})
        self.assertEqual(RpcMethod.parse_signature(self.add_method, "namespace.rpc_method(Number, Number) -> Number"), {"method_name": "namespace.rpc_method", "arguments": SortedDict([("param1", Number), ("param2", Number)]), "return_type": Number})
        self.assertEqual(RpcMethod.parse_signature(self.add_method, "namespace.rpc_method(String, String) -> String"), {"method_name": "namespace.rpc_method", "arguments": SortedDict([("param1", String), ("param2", String)]), "return_type": String})
        self.assertEqual(RpcMethod.parse_signature(self.add_method, "namespace.rpc_method(param1=String, param2=String) -> String"), {"method_name": "namespace.rpc_method", "arguments": SortedDict([("param1", String), ("param2", String)]), "return_type": String})
        self.assertEqual(RpcMethod.parse_signature(self.add_method, "namespace.rpc_method(String, param2=String) -> String"), {"method_name": "namespace.rpc_method", "arguments": SortedDict([("param1", String), ("param2", String)]), "return_type": String})


class JsonRpcFunctionalTestCase(unittest.TestCase):
    def test_validate_args(self):
        sig = 'jsonrpc(String, String) -> String'
        M = jsonrpc_method(sig, validate=True)(lambda r, s1, s2: s1+s2)
        self.assert_(validate_params(M, {'params': ['omg', u'wtf']}) is None)

        E = None
        try:
            validate_params(M, {'params': [['omg'], ['wtf']]})
        except Exception, e:
            E = e
        self.assert_(type(E) is InvalidParamsError)

    def test_validate_args_any(self):
        sig = 'jsonrpc(s1=Any, s2=Any)'
        M = jsonrpc_method(sig, validate=True)(lambda r, s1, s2: s1+s2)
        self.assert_(validate_params(M, {'params': ['omg', 'wtf']}) is None)
        self.assert_(validate_params(M, {'params': [['omg'], ['wtf']]}) is None)
        self.assert_(validate_params(M, {'params': {'s1': 'omg', 's2': 'wtf'}}) is None)

    def test_types(self):
        assert type(u'') == String
        assert type('') == String
        assert not type('') == Object
        assert not type([]) == Object
        assert type([]) == Array
        assert type('') == Any
        assert Any.kind('') == String
        assert Any.decode('str') == String
        assert Any.kind({}) == Object
        assert Any.kind(None) == Nil


class JsonRpcProtocolTestCase(TestCase):
    def setUp(self):
        if not User.objects.filter(username="sammeh").exists():
            User.objects.create_user(username='sammeh', email='sam@rf.com', password='password').save()
        self.host = "/json/"
        self.proxy10 = TestServiceProxy(self.host, version='1.0')
        self.proxy20 = TestServiceProxy(self.host, version='2.0')
        self.client = JsonRpcTestClient()

    def call(self, request_dict):
        response = self.client.post(self.host, json.dumps(request_dict),
                                                content_type="application/json-rpc")
        return json.loads(response.content)

    def test_10(self):
        self.assertEqual(
            self.proxy10.jsonrpc.test('this is a string')[u'result'], u'this is a string')

    def test_11(self):
        req = {
            u'version': u'1.1',
            u'method': u'jsonrpc.test',
            u'params': [u'this is a string'],
            u'id': u'holy-mother-of-god'
        }
        resp = self.call(req)
        self.assertEquals(resp[u'id'], req[u'id'])
        self.assertEquals(resp[u'result'], req[u'params'][0])

    def test_10_notify(self):
        pass

    def test_11_positional_mixed_args(self):
        req = {
            u'version': u'1.1',
            u'method': u'jsonrpc.strangeEcho',
            u'params': {u'1': u'this is a string', u'2': u'this is omg',
                        u'wtf': u'pants', u'nowai': 'nopants'},
            u'id': u'toostrange'
        }
        resp = self.call(req)
        self.assertEquals(resp[u'result'][-1], u'Default')
        self.assertEquals(resp[u'result'][1], u'this is omg')
        self.assertEquals(resp[u'result'][0], u'this is a string')
        self.assert_(u'error' not in resp)

    def test_11_GET(self):
        pass

    def test_11_GET_unsafe(self):
        pass

    def test_11_GET_mixed_args(self):
        params = {u'1': u'this is a string', u'2': u'this is omg',
                  u'wtf': u'pants', u'nowai': 'nopants'}
        url = "%s%s?%s" % (
            self.host, 'jsonrpc.strangeSafeEcho',
            (''.join(['%s=%s&' % (k, urllib.quote(v)) for k, v in params.iteritems()])).rstrip('&')
        )
        resp = json.loads(self.client.get(url).content)
        self.assertEquals(resp[u'result'][-1], u'Default')
        self.assertEquals(resp[u'result'][1], u'this is omg')
        self.assertEquals(resp[u'result'][0], u'this is a string')
        self.assert_(u'error' not in resp)

    def test_20_checked(self):
        self.assertEqual(
            self.proxy10.jsonrpc.varArgs('o', 'm', 'g')[u'result'],
            ['o', 'm', 'g']
        )
        self.assert_(self.proxy10.jsonrpc.varArgs(1,2,3)[u'error'])

    def test_11_service_description(self):
        pass

    def test_20_keyword_args(self):
        self.assertEqual(
            self.proxy20.jsonrpc.test(string='this is a string')[u'result'],
            u'this is a string')

    def test_20_positional_args(self):
        self.assertEqual(
            self.proxy20.jsonrpc.test('this is a string')[u'result'],
            u'this is a string')

    def test_20_notify(self):
        req = {
            u'jsonrpc': u'2.0',
            u'method': u'jsonrpc.notify',
            u'params': [u'this is a string'],
            u'id': None
        }
        resp = self.client.post(self.host, json.dumps(req),
                                content_type="application/json-rpc").content
        self.assertEquals(resp, '')

    def test_20_batch(self):
        req = [{
            u'jsonrpc': u'2.0',
            u'method': u'jsonrpc.test',
            u'params': [u'this is a string'],
            u'id': u'id-'+unicode(i)
        } for i in range(5)]
        resp = self.call(req)
        self.assertEquals(len(resp), len(req))
        for i, D in enumerate(resp):
            self.assertEquals(D[u'result'], req[i][u'params'][0])
            self.assertEquals(D[u'id'], req[i][u'id'])

    def test_20_batch_with_errors(self):
        req = [{
            u'jsonrpc': u'2.0',
            u'method': u'jsonrpc.test' if not i % 2 else u'jsonrpc.fails',
            u'params': [u'this is a string'],
            u'id': u'id-'+unicode(i)
        } for i in range(10)]
        resp = self.call(req)
        self.assertEquals(len(resp), len(req))
        for i, D in enumerate(resp):
            if not i % 2:
                self.assertEquals(D[u'result'], req[i][u'params'][0])
                self.assertEquals(D[u'id'], req[i][u'id'])
            else:
                self.assertEquals(D[u'result'], None)
                self.assert_(u'error' in D)
                self.assertEquals(D[u'error'][u'code'], 500)

    def test_authenticated_ok(self):
        self.assertEquals(
            self.proxy10.jsonrpc.testAuth(
                'sammeh', 'password', u'this is a string')[u'result'],
            u'this is a string')

    def test_authenticated_ok_kwargs(self):
        self.assertEquals(
            self.proxy20.jsonrpc.testAuth(
                username='sammeh', password='password', string=u'this is a string')[u'result'],
            u'this is a string')

    def test_authenticated_fail_kwargs(self):
        response = self.proxy20.jsonrpc.testAuth(username='osammeh', password='password', string=u'this is a string')
        self.assertEqual(response[u"error"] is not None, True)

    def test_authenticated_fail(self):
        response = self.proxy20.jsonrpc.testAuth('osammeh', 'password', u'this is a string')
        self.assertEqual(response[u"error"] is not None, True)

    def test_regr_bug_23(self):
        # system.describe was throwing the following error because return
        # types of methods weren't explicitly converted to strings:
        #
        #     <class 'jsonrpc.types.Any'> is not JSON serializable
        response = self.proxy10.system.describe()
        self.assertEqual(response["error"], None)
        self.assertEqual("procs" in response["result"], True)
        self.assertEqual(len(response["result"]["procs"]), 12)
        response = self.proxy20.system.describe()
        self.assertEqual(response["error"], None)
        self.assertEqual("procs" in response["result"], True)
        self.assertEqual(len(response["result"]["procs"]), 12)
