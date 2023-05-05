import os
import socket


def resolve_host():
    return os.environ.get('HOSTNAME', socket.gethostname())


def resolve_hostport():
    return int(os.environ.get('HOSTPORT', 2346))


def resolve_ns():
    return os.environ.get('NAMESERVER', socket.gethostname())


def resolve_nsport():
    return os.environ.get('NAMESERVER_PORT', 2346)


def resolve_dispatcher():
    return os.environ.get('DISPATCHER', socket.gethostname())


def resolve_dispatcher_port():
    return int(os.environ.get('DISPATCHER_PORT', 2346))
