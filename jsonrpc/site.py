from uuid import uuid1
import re
from inspect import getargspec
from django.http import HttpResponse
from django.utils.datastructures import SortedDict
from django.contrib.auth import authenticate
from jsonrpc._json import loads, dumps
from jsonrpc.exceptions import *
from jsonrpc.types import *
from django.core import signals


empty_dec = lambda f: f
try:
    from django.views.decorators.csrf import csrf_exempt
except (NameError, ImportError):
    csrf_exempt = empty_dec


from django.core.serializers.json import DjangoJSONEncoder


NoneType = type(None)
encode_kw = lambda p: dict([(str(k), v) for k, v in p.iteritems()])


KWARG_RE = re.compile(r'(?P<argument_name>[a-zA-Z0-9_]+)\s*' \
                      r'=\s*(?P<argument_type>[a-zA-Z]+)')
SIGNATURE_RE = re.compile(r"(?P<method_name>[a-zA-Z0-9._]*)\s*" \
                          r"(\((?P<argument_signature>[^)].*)?\)\s*" \
                          r"(\->\s*(?P<return_type>.*))?)?")


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


class RpcMethod(object):
    def __init__(self, func, signature="", allow_get=False):
        self.func = func
        self.__doc__ = func.__doc__
        self.__signature_data = self.parse_signature(func, signature)
        self.__name__ = self.__signature_data["method_name"]
        self.allow_get = allow_get

    @classmethod
    def parse_signature(cls, func, signature):
        argument_names = getargspec(func)[0][2 if getattr(func, "__self__", False) else 1:]
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
                    arguments[str(idx) if idx >= len(argument_names) else arguments.keys()[idx]] = _eval_arg_type(argument, None, argument, signature)
        return {"method_name": groups["method_name"] or func.__name__,
                "arguments": arguments,
                "return_type": _eval_arg_type(groups["return_type"], Any, 'return', signature) if groups["return_type"] else Any}

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


class AuthenticatedRpcMethod(RpcMethod):
    def __init__(self, *args, **kwargs):
        super(AuthenticatedRpcMethod, self).__init__(*args, **kwargs)
        self.prepend_argument("password", String)
        self.prepend_argument("username", String)

    def __call__(self, request, *args, **kwargs):
        user = None
        try:
            username, password = args[:2]
            user = authenticate(username=username, password=password)
            if user is not None:
                args = args[2:]
        except ValueError:
            if "username" in kwargs and "password" in kwargs:
                user = authenticate(username=kwargs["username"],
                                    password=kwargs["password"])
                if user is not None:
                    kwargs.pop("username")
                    kwargs.pop("password")
                else:
                    raise InvalidParamsError("Authenticated methods require at least [username, password] or {username: password:} arguments")
            if user is None:
                raise InvalidCredentialsError
        request.user = user
        return super(AuthenticatedRpcMethod, self).__call__(request, *args, **kwargs)


def encode_kw11(p):
    if not type(p) is dict:
        return {}
    ret = p.copy()
    removes = []
    for k, v in ret.iteritems():
        try:
            int(k)
        except ValueError:
            pass
        else:
            removes.append(k)
    for k in removes:
        ret.pop(k)
    return ret


def encode_arg11(p):
    if type(p) is list:
        return p
    elif not type(p) is dict:
        return []
    else:
        pos = []
        d = encode_kw(p)
        for k, v in d.iteritems():
            try:
                pos.append(int(k))
            except ValueError:
                pass
        pos = list(set(pos))
        pos.sort()
        return [d[str(i)] for i in pos]


def validate_params(method, *args, **kwargs):
    keys = method.signature_data["arguments"].keys()
    if len(args) + len(kwargs) < len(keys):
        raise InvalidParamsError('Not enough params provided for %s' % method.signature)
    elif len(args) + len(kwargs) > len(keys):
        raise InvalidParamsError('Too many params provided for %s' % method.signature)
    for idx, argument in enumerate(method.signature_data["arguments"].items()):
        if idx < len(args):
            if argument[0] in kwargs:
                raise InvalidParamsError("Ambiguous argument \"%s\"" % argument[0])
            if not Any.kind(args[idx]) == argument[1]:
                raise InvalidParamsError('%s is not the correct type %s for %s' % (type(args[idx]), argument[0], method.signature))
        else:
            if argument[0] not in kwargs:
                raise InvalidParamsError("Missing argument \"%s\"" % argument[0])
            if not Any.kind(kwargs[argument[0]]) == argument[1]:
                raise InvalidParamsError('%s is not the correct type %s for %s' % (type(kwargs[argument[0]]), argument[0], method.signature))


class JSONRPCSite(object):
    "A JSON-RPC Site"
    def __init__(self, name, version="1.0", json_encoder=DjangoJSONEncoder):
        self._urls = {}
        self.uuid = str(uuid1())
        self.version = version
        self.name = name
        self.register("system.describe", RpcMethod(self.describe, "system.describe"))
        self.json_encoder = json_encoder

    def register(self, name, method):
        self._urls[unicode(name)] = method

    def empty_response(self, version='1.0'):
        response = {'id': None, 'error': None, 'result': None}
        if version == '1.1':
            response['version'] = version
        elif version == '2.0':
            response['jsonrpc'] = version
        return response

    def validate_get(self, request, method):
        method = unicode(method)
        if method not in self._urls or not getattr(self._urls[method], 'allow_get', False):
            raise InvalidRequestError('The method you are trying to access is '
                                      'not available by GET requests')
        return {
          'params': dict([(k, v[0] if len(v) == 1 else v) for k, v in request.GET.lists()]),
          'method': method,
          'id': 'jsonrpc',
          'version': '1.1'
        }

    def response_dict(self, request, D, is_batch=False, version_hint='1.0', json_encoder=None):
        json_encoder = json_encoder or self.json_encoder
        version = version_hint
        response = self.empty_response(version=version)
        apply_version = {"2.0": lambda p: ([], encode_kw(p)) if type(p) is dict else (p, {}),
                         "1.1": lambda p: (encode_arg11(p), encode_kw(encode_kw11(p))),
                         "1.0": lambda p: (p, {})}

        try:
            if 'method' not in D or 'params' not in D:
                raise InvalidParamsError('Request requires str:"method" and list:"params"')
            if D['method'] not in self._urls:
                raise MethodNotFoundError('Method not found. Available methods: %s' % (
                              '\n'.join(self._urls.keys())))

            if 'jsonrpc' in D:
                if str(D['jsonrpc']) not in apply_version:
                    raise InvalidRequestError('JSON-RPC version %s not supported.' % D['jsonrpc'])
                version = request.jsonrpc_version = response['jsonrpc'] = str(D['jsonrpc'])
            elif 'version' in D:
                if str(D['version']) not in apply_version:
                    raise InvalidRequestError('JSON-RPC version %s not supported.' % D['version'])
                version = request.jsonrpc_version = response['version'] = str(D['version'])
            else:
                request.jsonrpc_version = '1.0'

            method = self._urls[str(D['method'])]
            args, kwargs = apply_version[version](D["params"])
            validate_params(method, *args, **kwargs)
            R = method(request, *args, **kwargs)

            encoder = json_encoder()
            if not sum(map(lambda e: isinstance(R, e), # type of `R` should be one of these or...
                      (dict, str, unicode, int, long, list, set, NoneType, bool))):
                try:
                    rs = encoder.default(R) # ...or something this thing supports
                except TypeError, exc:
                    raise TypeError("Return type not supported, for %r" % R)

            if 'id' in D and D['id'] is not None: # regular request
                response['result'] = R
                response['id'] = D['id']
                if version == '1.1' and 'error' in response:
                    response.pop('error')
            elif is_batch: # notification, not ok in a batch format, but happened anyway
                raise InvalidRequestError
            else: # notification
                return None, 204

            status = 200

        except Error, e:
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response['error'] = e.json_rpc_format
            if version == '1.1' and 'result' in response:
                response.pop('result')
            status = e.status
        except Exception, e:
            # exception missed by others
            signals.got_request_exception.send(sender=self.__class__, request=request)
            other_error = OtherError(e)
            response['error'] = other_error.json_rpc_format
            status = other_error.status
            if version == '1.1' and 'result' in response:
                response.pop('result')

        return response, status

    @csrf_exempt
    def dispatch(self, request, method='', json_encoder=None):
        if request.method.lower() == "options":
            return self.preflight(request)
        json_encoder = json_encoder or self.json_encoder

        try:
            # in case we do something json doesn't like, we always get back valid json-rpc response
            response = self.empty_response()
            if request.method.lower() == 'get':
                jsonrpc_request = self.validate_get(request, method)
            elif not request.method.lower() == 'post':
                raise RequestPostError
            else:
                try:
                    jsonrpc_request = loads(request.raw_post_data)
                except:
                    raise InvalidRequestError

            if type(jsonrpc_request) is list:
                response = [self.response_dict(request, d, is_batch=True, json_encoder=json_encoder)[0] for d in jsonrpc_request]
                status = 200
            else:
                response, status = self.response_dict(request, jsonrpc_request, json_encoder=json_encoder)
                if response is None and (not u'id' in jsonrpc_request or jsonrpc_request[u'id'] is None): # a notification
                    return HttpResponse('', status=status)

            json_rpc = dumps(response, cls=json_encoder)
        except Error, e:
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response['error'] = e.json_rpc_format
            status = e.status
            json_rpc = dumps(response, cls=json_encoder)
        except Exception, e:
            # exception missed by others
            signals.got_request_exception.send(sender=self.__class__, request=request)
            other_error = OtherError(e)
            response['result'] = None
            response['error'] = other_error.json_rpc_format
            status = other_error.status

            json_rpc = dumps(response, cls=json_encoder)

        response = HttpResponse(json_rpc, status=status, content_type='application/json-rpc')
        response["Access-Control-Allow-Origin"] = "*"
        return response

    def procedure_desc(self, key):
        M = self._urls[key]
        return {
            'name': M.signature_data["method_name"],
            'summary': M.__doc__,
            'idempotent': M.allow_get,
            'params': [{'type': str(Any.kind(t)), 'name': k}
                for k, t in M.signature_data["arguments"].iteritems()],
            'return': {'type': str(M.signature_data["return_type"])}}

    def service_desc(self):
        return {
            'sdversion': '1.0',
            'name': self.name,
            'id': 'urn:uuid:%s' % str(self.uuid),
            'summary': self.__doc__,
            'version': self.version,
            'procs': [self.procedure_desc(k)
                for k in self._urls.iterkeys()
                    if self._urls[k] != self.describe]}

    def describe(self, request):
        return self.service_desc()

    def preflight(self, request):
        accepts = request.META.get("HTTP_ACCEPT", "")
        content_type = "text/plain"
        for c_type in "application/json-rpc application/xml text/html".split():
            if c_type in accepts:
                content_type = c_type
                break
        response = HttpResponse(status=200, content_type=content_type)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        # TODO Use a whitelist of allowed headers
        response["Access-Control-Allow-Headers"] = request.META.get(
                                     "HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "")
        return response


jsonrpc_site = JSONRPCSite("django-json-rpc")
