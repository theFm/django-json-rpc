from jsonrpc.conf import default_site


@default_site.register("jsonrpc.test", public=True)
def echo(request, string):
    """Returns whatever you give it."""
    return string


@default_site.register("jsonrpc.testAuth")
def echo_auth(request, string):
    return string


@default_site.register("jsonrpc.notify", public=True)
def notify(request, string):
    pass


@default_site.register("jsonrpc.fails", public=True)
def fails(request, string):
    raise IndexError


@default_site.register("jsonrpc.strangeEcho", public=True)
def strange_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return [string, omg, wtf, nowai, yeswai]


@default_site.register("jsonrpc.safeEcho", public=True, idempotent=True)
def safe_echo(request, string):
    return string


@default_site.register("jsonrpc.strangeSafeEcho", public=True, idempotent=True)
def strange_safe_echo(request, string, omg, wtf, nowai, yeswai="Default"):
    return strange_echo(request, string, omg, wtf, nowai, yeswai)


@default_site.register("jsonrpc.checkedEcho(string=str, string2=str) -> str",
                                                  public=True, idempotent=True)
def protected_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.checkedArgsEcho(string=str, string2=str)",
                                                                   public=True)
def protected_args_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.checkedReturnEcho() -> String", public=True)
def protected_return_echo(request, string, string2):
    return string + string2


@default_site.register("jsonrpc.authCheckedEcho(Object, Array) -> Object",
                                                                   public=True)
def auth_checked_echo(request, obj1, arr1):
    return {"obj1": obj1, "arr1": arr1}


@default_site.register("jsonrpc.varArgs(String, String, str3=String) -> Array",
                                                                   public=True)
def checked_var_args_echo(request, *args, **kw):
    return list(args) + kw.values()
