import re

from functools import wraps

from jsonrpc.site import jsonrpc_site, RpcMethod, AuthenticatedRpcMethod
from jsonrpc.types import *
from jsonrpc.exceptions import *


default_site = jsonrpc_site
KWARG_RE_OLD = re.compile(
  r'\s*(?P<arg_name>[a-zA-Z0-9_]+)\s*=\s*(?P<arg_type>[a-zA-Z]+)\s*$')
SIG_RE = re.compile(
  r'\s*(?P<method_name>[a-zA-Z0-9._]+)\s*(\((?P<args_sig>[^)].*)?\)' \
  r'\s*(\->\s*(?P<return_sig>.*))?)?\s*$')


def jsonrpc_method(name, authenticated=False, safe=False, validate=False,
                   site=default_site):
    """
    Wraps a function turns it into a json-rpc method. Adds several attributes
    to the function speific to the JSON-RPC machinery and adds it to the default
    jsonrpc_site if one isn't provided. You must import the module containing
    these functions in your urls.py.

      name

          The name of your method. IE: `namespace.methodName` The method name
          can include type information, like `ns.method(String, Array) -> Nil`.

      authenticated=False

          Adds `username` and `password` arguments to the beginning of your
          method if the user hasn't already been authenticated. These will
          be used to authenticate the user against `django.contrib.authenticate`
          If you use HTTP auth or other authentication middleware, `username`
          and `password` will not be added, and this method will only check
          against `request.user.is_authenticated`.

          You may pass a callablle to replace `django.contrib.auth.authenticate`
          as the authentication method. It must return either a User or `None`
          and take the keyword arguments `username` and `password`.

      safe=False

          Designates whether or not your method may be accessed by HTTP GET.
          By default this is turned off.

      validate=False

          Validates the arguments passed to your method based on type
          information provided in the signature. Supply type information by
          including types in your method declaration. Like so:

          @jsonrpc_method('myapp.specialSauce(Array, String)', validate=True)
          def special_sauce(self, ingredients, instructions):
            return SpecialSauce(ingredients, instructions)

          Calls to `myapp.specialSauce` will now check each arguments type
          before calling `special_sauce`, throwing an `InvalidParamsError`
          when it encounters a discrepancy. This can significantly reduce the
          amount of code required to write JSON-RPC services.

      site=default_site

          Defines which site the jsonrpc method will be added to. Can be any
          object that provides a `register(name, func)` method.

    """
    def decorator(func):
        if authenticated:
            rpc_method = AuthenticatedRpcMethod(func, name, allow_get=safe)
        else:
            rpc_method = RpcMethod(func, name, allow_get=safe)
        site.register(rpc_method.signature_data["method_name"], rpc_method)
        return rpc_method
    return decorator
