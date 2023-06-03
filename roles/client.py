import os
from os import path
from typing import List

from common.environment import *
from common.job import Job
from common.printing import *
from common.setup import *
from Pyro5.api import Proxy
from Pyro5.errors import CommunicationError, NamingError
from roles.dispatcher import Dispatcher


def placework(dispatcher: Dispatcher, urls: List[str]):
    for url in urls:
        dispatcher.put_work(Job(url))


def writeresults(dispatcher: Dispatcher, count: int):
    os.makedirs(path.join('.', 'scrapped'), exist_ok=True)
    i = 0
    while i < count:
        try:
            result = dispatcher.get_result()
        except ValueError as e:
            continue
        try:
            file_name = path.join('.', 'scrapped', f'result_{i:04d}.json')
            with open(file_name, mode='wt') as file:
                file.write(repr(result.__dict__).replace('\\\'', '&&&').replace(
                    '"', '\\"').replace('\'', '"').replace('&&&', '\''))
            i += 1
        except Exception as e:
            error(
                f'Error writing results in file {file_name} for {result.url}. Shuting down client.\n')


def start():
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] CLIENT --', justify='center')
    print('\nInitializing client.\n')

    # Checking if dispatcher is up
    with CONSOLE.status("Checking connection with dispatcher...", spinner='line') as status:
        dispatcher = Proxy(
            f'PYRO:xscrap.dispatcher@{resolve_dispatcher()}:{resolve_dispatcher_port()}')
        try:
            dispatcher._pyroBind()
            uri = dispatcher._pyroUri
            # Good
            print(
                f'Successfully connected to dispatcher in {uri.host}:{uri.port}\n',
                style='c_good')
        # If dispatcher is down
        except CommunicationError as e:
            status.stop()
            error('Dispatcher not reachable. Shuting down client.\n\n')
            exit(1)
        # If name server is down
        except NamingError as e:
            status.stop()
            error('Name Server not reachable. Shuting down client.\n\n')
            exit(1)

    urls = []  # List of urls to scrap

    print(
        '\nWrite each url you want to scrap.\n' +
        '[c_beauty]♦[/c_beauty] To starting to scrap just type [c_beauty][bold][c_iprt]ENTER[/c_iprt][/bold][/c_beauty] in an empty line.\n'
        + '[c_beauty]♦[/c_beauty] To clear previous urls type [c_beauty][bold]clear[/bold][/c_beauty].\n' +
        '[c_beauty]♦[/c_beauty] To list previous urls type [c_beauty][bold]list[/bold][/c_beauty].\n' +
        '[c_beauty]♦[/c_beauty] To exit just type [c_beauty][bold]exit[/bold][/c_beauty].\n\n')

    # Main loop reading all the urls
    while True:
        print('[c_beauty]<>[/c_beauty]')
        url = input()

        # Command exit. Exit the client
        if url == 'exit':
            exit()
        # Command clear. Restart getting the urls
        if url == 'clear':
            urls.clear()
            continue
        # Command list. Show every URL written at the moment.
        if url == 'list':
            print(
                '\n'.join(('[c_beauty]•[/c_beauty] ' + url for url in urls)) +
                '\n')
            continue
        # Start sending URLs to scrap
        if url == '':
            # Connect to dispatcher
            count = len(urls)
            try:
                print('\n')
                with CONSOLE.status("Sending URLs to scrap...", spinner='line'):
                    placework(dispatcher, urls)  # Send the work
                print(f'URLs sended successfully.\n',
                      style='c_good')
            # If dispatcer is down
            except CommunicationError as e:
                error(
                    'Dispatcher not reachable. Try again. (Previous urls saved)\n\n')
                continue
            # If name server is down
            except NamingError as e:
                status.stop()
                error(
                    'Name Server not reachable. Try again. (Previous urls saved)\n\n')
                continue
            try:
                with CONSOLE.status("Waiting for results", spinner='line'):
                    writeresults(dispatcher, count)  # Get results
                print(
                    f'Results stored in [bold][c_iprt]./scrapped[/c_iprt][/bold] successfully.\n\n',
                    style='c_good')
            # If dispatcer is down
            except CommunicationError as e:
                error(
                    'Dispatcher not reachable. Try again. (Previous urls saved)\n\n')
                continue
            # If name server is down
            except NamingError as e:
                status.stop()
                error(
                    'Name Server not reachable. Try again. (Previous urls saved)\n\n')
                continue
            urls.clear()
        else:
            urls.append(url)
