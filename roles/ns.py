from Pyro5.nameserver import start_ns_loop
from common.printing import *


def start(hostname: str, port: int | None = None):
    # Beauty Printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] NAME SERVER --', justify='center')
    print('\nInitializing Name Server.\n')
    # Application Wrap for Pyro5 Name Server
    start_ns_loop(hostname, port)
