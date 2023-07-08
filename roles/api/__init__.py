import asyncio
from subprocess import DEVNULL, Popen
import sys
import time
from math import log2
from random import random
from typing import Iterable, List

import uvicorn
from common.environment import *
from fastapi import FastAPI, Request
from pydantic import AnyUrl, BaseModel
from Pyro5.api import Proxy
from Pyro5.errors import CommunicationError
from roles.dispatcher import Dispatcher, get_dispatcher, check_is_there
from sse_starlette.sse import EventSourceResponse
from common.printing import *

app = FastAPI()

WAIT_INCREMENT = 0.5
WAIT_REDUCTION = 2

__spawning_dispatcher=False

def undying_get_dispatcher():
    global __spawning_dispatcher
    if not __spawning_dispatcher:
        while not check_is_there():
            try:
                get_dispatcher()
            except Exception as e:
                if str(e).startswith('XSCRAP:Orphan'):
                    log("Dispatcher node missing.")
                    __spawning_dispatcher=True
                    log("Spawning dispatcher...")
                    
                    os.environ['DISPATCHER']=resolve_host()
                    os.environ['DISPATCHER_PORT']=str(resolve_dispatcher_port())
                    
                    try:
                        _ = Popen([sys.executable,os.path.abspath(sys.argv[0]),"dispatcher"], 
                                stdout=DEVNULL, stdin=DEVNULL, stderr=DEVNULL)
                    except Exception as e:
                        error("Local dispatcher can't be spawned. Reason:")
                        print(e)
                        print('\n')
                    else:
                        log(f"Spawned dispatcher at: {resolve_cache_server()}")
                        __spawning_dispatcher=False
                        return get_dispatcher()
                
        time.sleep(4)
            
    return get_dispatcher()

def fetch_result(url: str):
    '''
    Tries to get the result for scrapping the URL and keeps trying until it has it
    '''
    wait_time = 1
    dispatcher = undying_get_dispatcher()
    while True:
        try:
            r = dispatcher.get_result_single(url)
        except CommunicationError:
            dispatcher = undying_get_dispatcher()
            r = dispatcher.get_result_single(url)
        if r is not None:
            wait_time = 1
            return r
        time.sleep(log2(wait_time)//WAIT_REDUCTION)
        wait_time += WAIT_INCREMENT


def request_result(urls: List[str]):
    '''
    Works like a signal for the dispatcher that he need to have this urls in cache
    '''
    # TODO: Improve this behavior.
    # The goal of this is to enqueue all needed url before you try with fetch_result
    # to have the result
    dispatcher = undying_get_dispatcher()
    try:
        dispatcher.get_result(urls)
    except CommunicationError:
        dispatcher = undying_get_dispatcher()
        dispatcher.get_result(urls)


async def deliver_async(urls: List[str]):
    # Connect to dispatcher
    # TODO: Manage desconnection and other problems
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, request_result, urls)
    for url in urls:
        yield await loop.run_in_executor(None, fetch_result, url)


class Batch(BaseModel):
    urls: List[AnyUrl]


@app.post("/scrap")
async def scrap(request: Request, batch: Batch):
    async def event_stream():
        async for result in deliver_async([str(url) for url in batch.urls]):
            yield str(result)

    return EventSourceResponse(event_stream())


@app.post("/reset")
async def scrap(request: Request, batch: Batch):
    dispatcher = undying_get_dispatcher()
    try:
        dispatcher.clear_cache(batch.urls)
    except CommunicationError:
        dispatcher = undying_get_dispatcher()
        dispatcher.clear_cache(batch.urls)


def start():
    uvicorn.run(app, host=resolve_api_host(), port=resolve_api_port())
