from fire import Fire

# Roles import
import roles.client as client
import roles.dispatcher as dispatcher
import roles.worker as worker

# Roles register
ROLES = {
    'client': client,
    'dispatcher': dispatcher,
    'worker': worker,
}

ROLES = {k: v.start for k, v in ROLES.items()}

Fire(ROLES)
