from jsonrpc import jsonrpc_method


@jsonrpc_method("jsonrpc.test")
def echo(request, string):
    """Returns whatever you give it."""
    return string


@jsonrpc_method("jsonrpc.testAuth", authenticated=True)
def echo_auth(request, string):
    return string


@jsonrpc_method("jsonrpc.notify")
def notify(request, string):
    pass


@jsonrpc_method("jsonrpc.fails")
def fails(request, string):
    raise IndexError


@jsonrpc_method("jsonrpc.strangeEcho")
def strange_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return [string, omg, wtf, nowai, yeswai]


@jsonrpc_method("jsonrpc.safeEcho", safe=True)
def safe_echo(request, string):
    return string


@jsonrpc_method("jsonrpc.strangeSafeEcho", safe=True)
def strange_safe_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return strange_echo(request, string, omg, wtf, nowai, yeswai)


@jsonrpc_method("jsonrpc.checkedEcho(string=str, string2=str) -> str",
                                                      safe=True, validate=True)
def protected_echo(request, string, string2):
    return string + string2


@jsonrpc_method("jsonrpc.checkedArgsEcho(string=str, string2=str)",
                                                                 validate=True)
def protected_args_echo(request, string, string2):
    return string + string2


@jsonrpc_method("jsonrpc.checkedReturnEcho() -> String", validate=True)
def protected_return_echo(request, string, string2):
    return string + string2


@jsonrpc_method("jsonrpc.authCheckedEcho(Object, Array) -> Object",
                                                                 validate=True)
def auth_checked_echo(request, obj1, arr1):
    return {"obj1": obj1, "arr1": arr1}


@jsonrpc_method("jsonrpc.varArgs(String, String, str3=String) -> Array",
                                                                 validate=True)
def checked_var_args_echo(request, *args, **kw):
    return list(args) + kw.values()
