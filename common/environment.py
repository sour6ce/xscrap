###############################################################################
#
# COMMON CODE RELATED TO ENVIRONMENT VARIABLES
#
###############################################################################

import os
import socket


def resolve_docker():
    return 'IN_DOCKER' in os.environ.keys()


def resolve_worker_amount():
    return int(os.environ.get('WORKER_AMOUNT', 3))


def resolve_workertiemout():
    return int(os.environ.get('WORKER_TIMEOUT', 60))


def resolve_host():
    if resolve_docker():
        return '0.0.0.0'
    return os.environ.get('HOSTNAME', socket.gethostname())


def resolve_hostport():
    return int(os.environ.get('HOSTPORT', 8000))


def resolve_dispatcher():
    if resolve_docker():
        return '0.0.0.0'
    return os.environ.get('DISPATCHER', socket.gethostname())


def resolve_backup_dispatcher():
    return os.environ.get(
        'BACKUP_DISPATCHER', None
        if 'BACKUP_DISPATCHER_PORT' not in os.environ.keys() else
        resolve_host())


def resolve_dispatcher_port():
    return int(os.environ.get('DISPATCHER_PORT', 8000))


def resolve_backup_dispatcher_port():
    if 'BACKUP_DISPATCHER_PORT' in os.environ.keys() or 'BACKUP_DISPATCHER' in os.environ.keys():
        return int(os.environ.get('BACKUP_DISPATCHER_PORT', 8000))
    else:
        return None


def resolve_api_host():
    return os.environ.get('API_HOST', resolve_host())


def resolve_api_port():
    return int(os.environ.get('API_PORT', os.environ.get('HOSTPORT', 6900)))


def resolve_cache_host():
    return os.environ.get('CACHE_SERVER_HOST', resolve_host())


def resolve_cache_port():
    return int(
        os.environ.get('CACHE_SERVER_PORT', os.environ.get('HOSTPORT', 6380)))


def resolve_cache_server():
    return os.environ.get(
        'CACHE_SERVER_URL',
        f'PYRO:xscrap.cache@{resolve_cache_host()}:{resolve_cache_port()}')


def resolve_pending_queue_maxsize():
    return int(os.environ.get('PENDING_QUEUE_MAXSIZE', '10000'))


def resolve_cache_maxsize():
    return int(os.environ.get('CACHE_MAXSIZE', '100000'))


def resolve_mbb_retries():
    return int(os.environ.get('MBB_RETRIES', 5))


def resolve_mbb_time():
    return int(os.environ.get('MBB_TIME', 1))
