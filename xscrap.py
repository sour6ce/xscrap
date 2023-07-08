from fire import Fire

# Roles import
import roles.client as client
import roles.dispatcher as dispatcher
import roles.worker as worker
import roles.api as api
import roles.api_cli as api_cli
import roles.cache as cache

# Roles register
ROLES = {
    'client': client,
    'dispatcher': dispatcher,
    'worker': worker,
    'cli': api_cli,
    'api': api,
    'cache': cache
}

ROLES = {k: v.start for k, v in ROLES.items()}

Fire(ROLES)
