from Pyro5.api import Proxy, register_dict_to_class
from common.job import Job
import os
from os import path
from roles.dispatcher import Dispatcher
from typing import List


# Registered how to cast from dict to class
register_dict_to_class(
    f'{Job.__module__}.{Job.__name__}', Job.from_dict)


def placework(dispatcher: Dispatcher, urls: List[str]):
    for url in urls:
        dispatcher.put_work(Job(url))


def writeresults(dispatcher: Dispatcher, count: int):
    os.makedirs(path.join('.', 'scrapped'), exist_ok=True)
    i = 0
    while i < count:
        result = dispatcher.get_result()
        with open(path.join('.', 'scrapped', f'result_{i:04d}.json'), mode='wt') as file:
            file.write(repr(result.__dict__).replace('\'', '\"').replace(
                '{', '{\n\t').replace(',', ',\n\t').replace('}', '\n}'))
        i += 1


def start():
    urls = []
    while True:
        print('<>', end='')
        url = input()
        if url.startswith('exit'):
            exit()
        else:
            if url == '':
                with Proxy('PYRONAME:xscrap.dispatcher') as dispatcher:
                    count = len(urls)
                    placework(dispatcher, urls)
                    writeresults(dispatcher, count)
            else:
                urls.append(url)
