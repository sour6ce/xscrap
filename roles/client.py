import os
from os import path
import time
from typing import List

from common.environment import *
from common.job import Job
from common.printing import *
from common.setup import *
from Pyro5.api import Proxy
from Pyro5.errors import CommunicationError, NamingError
from roles.dispatcher import Dispatcher, get_dispatcher, check_is_there

CLIENT_CONNECTION_RETRIES=15

def placework(dispatcher: Dispatcher, urls: List[str]):
    dispatcher.put_work(urls)


def writeresults(dispatcher: Dispatcher, urls: List[str]):
    while any(True if r is None else False for r in dispatcher.get_result(urls)):
        time.sleep(0.4)


def start():
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] CLIENT --', justify='center')
    print('\nInitializing client.\n')

    dispatcher = get_dispatcher()
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
            if not check_is_there():
                dispatcher = get_dispatcher(CLIENT_CONNECTION_RETRIES)
            log(f'{dispatcher}')
            if dispatcher is None:
                error('Dispatcher not reachable. Try again. (Previous urls saved)\n\n')
                continue

            print('\n')
            with CONSOLE.status("Sending URLs to scrap...", spinner='line') as status:
                try: 
                    placework(dispatcher, urls)  # Send the work
                except CommunicationError or NamingError:
                    dispatcher = get_dispatcher(CLIENT_CONNECTION_RETRIES)
                    if dispatcher is None:
                        error('Dispatcher not reachable. Try again. (Previous urls saved)\n\n')
                        continue
                except Exception as e:
                    raise e
            print(f'URLs sent successfully.\n',
                    style='c_good')
            
            with CONSOLE.status("Waiting for results", spinner='line'):
                try:
                    writeresults(dispatcher, urls)  # Get results
                except CommunicationError or NamingError:
                    dispatcher = get_dispatcher()
                    if dispatcher is None:
                        error('Dispatcher not reachable. Try again. (Previous urls saved)\n\n')
                        continue
                except Exception as e:
                    raise e
            print(
                f'Results returned successfully.\n\n',
                style='c_good')
            
            urls.clear()
        else:
            urls.append(url)
