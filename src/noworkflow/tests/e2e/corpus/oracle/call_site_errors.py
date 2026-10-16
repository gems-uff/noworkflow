"""Errors that Python reports at the call site name the callee
(#NEW:call-error-names-collector)

A keyword given twice through two ``**`` unpackings is rejected before the
callee runs, and the message names the function called; a configuration
loader shows that message to its user. A ``TypeError`` raised while the
callee binds its parameters is in arguments.py.
"""


def connect(host, *, port=80, **options):
    return host, port, sorted(options)


defaults = {"port": 8080, "timeout": 3}
overrides = {"port": 9090}
try:
    connect("db", **defaults, **overrides)
except TypeError as error:
    print("rejected:", error)
print(connect("db", **dict(defaults, **overrides)))
