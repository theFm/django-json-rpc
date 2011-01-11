from uuid import uuid1
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


def validate_params(method, D):
    if type(D['params']) == Object:
        keys = method.json_arg_types.keys()
        if len(keys) != len(D['params']):
            raise InvalidParamsError('Not eough params provided for %s' % method.json_sig)
        for k in keys:
            if not k in D['params']:
                raise InvalidParamsError('%s is not a valid parameter for %s'
                                         % (k, method.json_sig))
            if not Any.kind(D['params'][k]) == method.json_arg_types[k]:
                raise InvalidParamsError('%s is not the correct type %s for %s'
                                          % (type(D['params'][k]),
                                             method.json_arg_types[k],
                                             method.json_sig))
    elif type(D['params']) == Array:
        arg_types = method.json_arg_types.values()
        try:
            for i, arg in enumerate(D['params']):
                if not Any.kind(arg) == arg_types[i]:
                    raise InvalidParamsError('%s is not the correct type %s for %s'
                          % (type(arg), arg_types[i], method.json_sig))
        except IndexError:
            raise InvalidParamsError('Too many params provided for %s' % method.json_sig)
        else:
            if len(D['params']) != len(arg_types):
                raise InvalidParamsError('Not enough params provided for %s' % method.json_sig)


class JSONRPCSite(object):
    "A JSON-RPC Site"
    def __init__(self, name, version="1.0", json_encoder=DjangoJSONEncoder):
        self._urls = {}
        self.uuid = str(uuid1())
        self.version = version
        self.name = name
        self.register("system.describe", self.describe)
        self.json_encoder = json_encoder

    def register(self, name, method):
        self._urls[unicode(name)] = method

    def empty_response(self, version='1.0'):
        resp = {'id': None}
        if version == '1.1':
            resp['version'] = version
            return resp
        if version == '2.0':
            resp['jsonrpc'] = version
        resp.update({'error': None, 'result': None})
        return resp

    def validate_get(self, request, method):
        method = unicode(method)
        if method not in self._urls or not getattr(self._urls[method], 'json_safe', False):
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
        apply_version = {'2.0': lambda f, r, p: f(r, **encode_kw(p)) if type(p) is dict else f(r, *p),
                         '1.1': lambda f, r, p: f(r, *encode_arg11(p), **encode_kw(encode_kw11(p))),
                         '1.0': lambda f, r, p: f(r, *p)}

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
            if getattr(method, 'json_validate', False):
                validate_params(method, D)
            R = apply_version[version](method, request, D['params'])

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
        from django.http import HttpResponse
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
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    def procedure_desc(self, key):
        M = self._urls[key]
        return {
            'name': M.json_method,
            'summary': M.__doc__,
            'idempotent': M.json_safe,
            'params': [{'type': str(Any.kind(t)), 'name': k}
                for k, t in M.json_arg_types.iteritems()],
            'return': {'type': str(M.json_return_type)}}

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


jsonrpc_site = JSONRPCSite("django-json-rpc")
