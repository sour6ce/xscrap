from fire import Fire

# Roles import
import roles.client as client
import roles.dispatcher as dispatcher
import roles.worker as worker
import roles.api as api
import roles.api_cli as api_cli

# Roles register
ROLES = {
    'client': client,
    'dispatcher': dispatcher,
    'worker': worker,
    'cli': api_cli,
    'api': api
}

ROLES = {k: v.start for k, v in ROLES.items()}

Fire(ROLES)
