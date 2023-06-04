###############################################################################
#
# COMMON CODE RELATED TO INITIAL PROCESSING
#
###############################################################################

from Pyro5.api import register_dict_to_class
import Pyro5

from common.job import Job

# Registered how to cast from dict to class
register_dict_to_class(
    f'{Job.__module__}.{Job.__name__}', Job.from_dict)

Pyro5.config.COMPRESSION = True
Pyro5.config.SERIALIZER = 'marshal'

EARLY_ERROR_STATUS_CODE = 580
