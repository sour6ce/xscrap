###############################################################################
#
# COMMON CODE RELATED TO ENVIRONMENT VARIABLES
#
###############################################################################

import os
import socket


def resolve_host():
    return os.environ.get('HOSTNAME', socket.gethostname())


def resolve_hostport():
    return int(os.environ.get('HOSTPORT', 2346))


def resolve_dispatcher():
    return os.environ.get('DISPATCHER', socket.gethostname())


def resolve_dispatcher_port():
    return int(os.environ.get('DISPATCHER_PORT', 2346))


def resolve_redis():
    return os.environ.get(
        'REDIS_URL',
        f'redis://{os.environ.get("REDIS_HOST","127.0.0.1")}:{os.environ.get("REDIS_PORT","6379")}')
