import unittest
from django.test import TestCase
from jsonrpc import jsonrpc_method, _parse_sig, Any, SortedDict
from jsonrpc.exceptions import InvalidParamsError
from jsonrpc.proxy import TestServiceProxy
from jsonrpc.site import validate_params
from jsonrpc.types import String, Object, Array, Nil


# Register JSON-RPC methods
import jsonrpc.tests.methods


class JSONRPCFunctionalTests(unittest.TestCase):
    def test_method_parser(self):
        working_sigs = [
            ('jsonrpc', 'jsonrpc', SortedDict(), Any),
            ('jsonrpc.methodName', 'jsonrpc.methodName', SortedDict(), Any),
            ('jsonrpc.methodName() -> list', 'jsonrpc.methodName', SortedDict(), list),
            ('jsonrpc.methodName(str, str, str ) ', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', str)]), Any),
            ('jsonrpc.methodName(str, b=str, c=str)', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', str)]), Any),
            ('jsonrpc.methodName(str, b=str) -> dict', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str)]), dict),
            ('jsonrpc.methodName(str, str, c=Any) -> Any', 'jsonrpc.methodName', SortedDict([('a', str), ('b', str), ('c', Any)]), Any),
            ('jsonrpc(Any ) ->  Any', 'jsonrpc', SortedDict([('a', Any)]), Any),
        ]
        error_sigs = [
            ('jsonrpc(str) -> nowai', ValueError),
            ('jsonrpc(nowai) -> Any', ValueError),
            ('jsonrpc(nowai=str, str)', ValueError),
            ('jsonrpc.methodName(nowai*str) -> Any', ValueError)
        ]
        for sig in working_sigs:
            ret = _parse_sig(sig[0], list(iter(sig[2])))
            self.assertEquals(ret[0], sig[1])
            self.assertEquals(ret[1], sig[2])
            self.assertEquals(ret[2], sig[3])
        for sig in error_sigs:
            e = None
            try:
                _parse_sig(sig[0], ['a'])
            except Exception, exc:
                e = exc
            self.assert_(type(e) is sig[1])

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
