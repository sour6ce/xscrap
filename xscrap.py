from fire import Fire

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

ROLES = {k: v.start for k, v in ROLES.items()}

Fire(ROLES)
