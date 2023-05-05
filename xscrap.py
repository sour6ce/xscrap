from fire import Fire

# Roles import
import roles.direct.client as client
import roles.direct.dispatcher as dispatcher
import roles.direct.worker as worker

# Roles register
ROLES = {
    'client': client,
    'dispatcher': dispatcher,
    'worker': worker,
}

ROLES = {k: v.start for k, v in ROLES.items()}

Fire(ROLES)
