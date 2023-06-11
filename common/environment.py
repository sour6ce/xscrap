###############################################################################
#
# COMMON CODE RELATED TO ENVIRONMENT VARIABLES
#
###############################################################################

import os
import socket


def resolve_docker():
    return 'IN_DOCKER' in os.environ.keys()

def resolve_host():
    if resolve_docker(): return '0.0.0.0'
    return os.environ.get('HOSTNAME', socket.gethostname())


def resolve_hostport():
    return int(os.environ.get('HOSTPORT', 8000))


def resolve_dispatcher():
    if resolve_docker():
        return '0.0.0.0'
    return os.environ.get('DISPATCHER', socket.gethostname())


def resolve_backup_dispatcher():
    return os.environ.get('BACKUP_DISPATCHER', None)


def resolve_dispatcher_port():
    return int(os.environ.get('DISPATCHER_PORT', 8000))


def resolve_backup_dispatcher_port():
    if 'BACKUP_DISPATCHER_PORT' in os.environ.keys():
        return int(os.environ.get('BACKUP_DISPATCHER_PORT', 8000))
    else:
        return None


def resolve_api_host():
    return os.environ.get('API_HOST', resolve_host())


def resolve_api_port():
    return int(os.environ.get('API_PORT', os.environ.get('HOSTPORT', 8000)))


def resolve_redis():
    return os.environ.get(
        'REDIS_URL',
        f'redis://{os.environ.get("REDIS_HOST","127.0.0.1")}:{os.environ.get("REDIS_PORT","6379")}')


def resolve_backup_redis():
    return os.environ.get('BACKUP_REDIS_URL',None)


def resolve_mbb_retries():
    return int(os.environ.get('MBB_RETRIES',5))

def resolve_mbb_time():
    return int(os.environ.get('MBB_TIME',1))