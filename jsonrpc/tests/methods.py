from jsonrpc.site import default_site


@default_site.register("jsonrpc.test")
def echo(request, string):
    """Returns whatever you give it."""
    return string


@default_site.register("jsonrpc.testAuth", authenticated=True)
def echo_auth(request, string):
    return string


@default_site.register("jsonrpc.notify")
def notify(request, string):
    pass


@default_site.register("jsonrpc.fails")
def fails(request, string):
    raise IndexError


@default_site.register("jsonrpc.strangeEcho")
def strange_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return [string, omg, wtf, nowai, yeswai]


@default_site.register("jsonrpc.safeEcho", safe=True)
def safe_echo(request, string):
    return string


@default_site.register("jsonrpc.strangeSafeEcho", safe=True)
def strange_safe_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return strange_echo(request, string, omg, wtf, nowai, yeswai)


@default_site.register("jsonrpc.checkedEcho(string=str, string2=str) -> str",
                                                                     safe=True)
def protected_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.checkedArgsEcho(string=str, string2=str)")
def protected_args_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.checkedReturnEcho() -> String")
def protected_return_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.authCheckedEcho(Object, Array) -> Object")
def auth_checked_echo(request, obj1, arr1):
    return {"obj1": obj1, "arr1": arr1}


@default_site.register("jsonrpc.varArgs(String, String, str3=String) -> Array")
def checked_var_args_echo(request, *args, **kw):
    return list(args) + kw.values()
