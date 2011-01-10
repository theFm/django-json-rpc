import re
from inspect import getargspec
from functools import wraps
from django.utils.datastructures import SortedDict
from jsonrpc.site import jsonrpc_site
from jsonrpc.types import *
from jsonrpc.exceptions import *


default_site = jsonrpc_site
KWARG_RE = re.compile(r'(?P<argument_name>[a-zA-Z0-9_]+)\s*' \
                      r'=\s*(?P<argument_type>[a-zA-Z]+)')
SIGNATURE_RE = re.compile(r"(?P<method_name>[a-zA-Z0-9._]*)\s*" \
                          r"(\((?P<argument_signature>[^)].*)?\)\s*" \
                          r"(\->\s*(?P<return_type>.*))?)?")
KWARG_RE_OLD = re.compile(
  r'\s*(?P<arg_name>[a-zA-Z0-9_]+)\s*=\s*(?P<arg_type>[a-zA-Z]+)\s*$')
SIG_RE = re.compile(
  r'\s*(?P<method_name>[a-zA-Z0-9._]+)\s*(\((?P<args_sig>[^)].*)?\)' \
  r'\s*(\->\s*(?P<return_sig>.*))?)?\s*$')


class JSONRPCTypeCheckingUnavailable(Exception):
    pass


class RpcMethod(object):
    def __init__(self, func, signature=""):
        self.func = func
        self.__doc__ = func.__doc__
        self.__signature_data = self.parse_signature(func, signature)
        self.__name__ = self.__signature_data["method_name"]

    @classmethod
    def parse_signature(cls, func, signature):
        argument_names = getargspec(func)[0][1:]
        arguments = SortedDict([(argument_name, Any) for argument_name in argument_names])
        seen_positional_arguments = False
        m = SIGNATURE_RE.match(signature)
        if m is None:
            raise ValueError("Invalid method signature %s" % repr(signature))
        groups = m.groupdict()
        if groups["argument_signature"] and groups["argument_signature"].strip():
            for idx, argument in enumerate(groups["argument_signature"].strip().split(",")):
                argument = argument.strip()
                if "=" in argument:
                    m = KWARG_RE.match(argument)
                    if not m:
                        raise ValueError("Can not parse argument type %s in %s" % (repr(argument), repr(signature)))
                    argument_name = m.groupdict()["argument_name"].strip()
                    argument_type = m.groupdict()["argument_type"].strip()
                    if not (argument_name or argument_type):
                        raise ValueError("Invalid keyword argument value %s in %s" % (repr(argument), repr(signature)))
                    arguments[argument_name] = _eval_arg_type(argument_type, None, argument, signature)
                    seen_positional_arguments = True
                else:
                    if seen_positional_arguments:
                        raise ValueError("Positional arguments must occur before keyword arguments in %s" % repr(signature))
                    if len(arguments) <= idx:
                        arguments[str(idx)] = _eval_arg_type(argument, None, argument, signature)
                    else:
                        arguments[arguments.keys()[idx]] = _eval_arg_type(argument, None, argument, signature)
        return {"method_name": groups["method_name"] or func.__name__,
                "arguments": arguments,
                "return_type": groups["return_type"]}

    @property
    def signature_data(self):
        return self.__signature_data

    @property
    def signature(self):
        signature = self.__signature_data["method_name"]
        signature += "(%s)" % ", ".join(["%s=%s" % item for item in self.__signature_data["arguments"].items()])
        if self.__signature_data["return_type"]:
            signature += " -> %s" % self.__signature_data["return_type"]
        return signature

    def prepend_argument(self, argument_name, argument_type=Any):
        self.__signature_data["arguments"].insert(0, argument_name, argument_type)

    def __call__(self, request, *args, **kwargs):
        return self.func(request, *args, **kwargs)


def _type_checking_available(sig='', validate=False):
    if not hasattr(type, '__eq__') and validate: # and False:
        raise JSONRPCTypeCheckingUnavailable(
          'Type checking is not available in your version of Python '
          'which is only available in Python 2.6 or later. Use Python 2.6 '
          'or later or disable type checking in %s' % sig)


def _eval_arg_type(arg_type, T=Any, arg=None, sig=None):
    """
    Returns a type from a snippit of python source. Should normally be
    something just like 'str' or 'Object'.

      arg_type      the source to be evaluated
      T             the default type
      arg           context of where this type was extracted
      sig           context from where the arg was extracted

    Returns a type or a Type
    """
    try:
        T = eval(arg_type)
    except Exception, e:
        raise ValueError('The type of %s could not be evaluated in %s for %s: %s' %
                         (arg_type, arg, sig, str(e)))
    else:
        if type(T) not in (type, Type):
            raise TypeError('%s is not a valid type in %s for %s' %
                            (repr(T), arg, sig))
        return T


def _inject_args(sig, types):
    """
    A function to inject arguments manually into a method signature before
    it's been parsed. If using keyword arguments use 'kw=type' instead in
    the types array.

      sig     the string signature
      types   a list of types to be inserted

    Returns the altered signature.
    """
    if '(' in sig:
        parts = sig.split('(')
        sig = '%s(%s%s%s' % (
          parts[0], ', '.join(types),
          (', ' if parts[1].index(')') > 0 else ''), parts[1]
        )
    else:
        sig = '%s(%s)' % (sig, ', '.join(types))
    return sig


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
        rpc_method = RpcMethod(func, name)
        if authenticated:
            if authenticated is True:
                rpc_method.prepend_argument("username", String)
                rpc_method.prepend_argument("password", String)
                from django.contrib.auth import authenticate
                from django.contrib.auth.models import User
            else:
                authenticate = authenticated
            @wraps(rpc_method)
            def _func(request, *args, **kwargs):
                user = getattr(request, 'user', None)
                is_authenticated = getattr(user, 'is_authenticated', lambda: False)
                if ((user is not None
                      and callable(is_authenticated) and not is_authenticated())
                    or user is None):
                    user = None
                    try:
                        creds = args[:2]
                        user = authenticate(username=creds[0], password=creds[1])
                        if user is not None:
                            args = args[2:]
                    except IndexError:
                        if 'username' in kwargs and 'password' in kwargs:
                            user = authenticate(username=kwargs['username'],
                                                password=kwargs['password'])
                            if user is not None:
                                kwargs.pop('username')
                                kwargs.pop('password')
                        else:
                            raise InvalidParamsError(
                                'Authenticated methods require at least '
                                '[username, password] or {username: password:} arguments')
                    if user is None:
                        raise InvalidCredentialsError
                    request.user = user
                return rpc_method(request, *args, **kwargs)
        else:
            _func = rpc_method
        _func.json_args = rpc_method.signature_data["arguments"].keys()
        _func.json_arg_types = rpc_method.signature_data["arguments"]
        _func.json_return_type = rpc_method.signature_data["return_type"]
        _func.json_method = rpc_method.signature_data["method_name"]
        _func.json_safe = safe
        _func.json_sig = rpc_method.signature
        _func.json_validate = validate
        site.register(rpc_method.signature_data["method_name"], _func)
        return _func
    return decorator
