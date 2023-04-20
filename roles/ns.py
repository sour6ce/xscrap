from Pyro5.nameserver import start_ns_loop


def start(hostname: str, port: int | None = None):
    # Application Wrap for Pyro5 Name Server
    start_ns_loop(hostname, port)
