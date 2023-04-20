from fire import Fire
from enum import Enum

# Roles import
import roles.client as client
import roles.dispatcher as dispatcher
import roles.worker as worker
import roles.ns as ns

# Roles register
ROLES = {
    'client': client,
    'dispatcher': dispatcher,
    'worker': worker,
    'ns': ns,
}


def start(role: str, /, **args):
    ROLES[role].start(**args)


Fire(start)
