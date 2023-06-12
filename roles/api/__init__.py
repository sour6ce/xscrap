import asyncio
import time
from math import log2
from random import random
from typing import Iterable, List

import uvicorn
from common.environment import (resolve_api_port, resolve_dispatcher,
                                resolve_dispatcher_port, resolve_host)
from fastapi import FastAPI, Request
from pydantic import AnyUrl, BaseModel
from Pyro5.api import Proxy
from Pyro5.errors import CommunicationError
from roles.dispatcher import Dispatcher, get_dispatcher
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

WAIT_INCREMENT = 0.5
WAIT_REDUCTION = 2


def fetch_result(url: str):
    '''
    Tries to get the result for scrapping the URL and keeps trying until it has it
    '''
    wait_time = 1
    dispatcher = get_dispatcher()
    while True:
        try:
            r = dispatcher.get_result_single(url)
        except CommunicationError:
            dispatcher = get_dispatcher()
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
    dispatcher = get_dispatcher()
    try:
        dispatcher.get_result(urls)
    except CommunicationError:
        dispatcher = get_dispatcher()
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
    dispatcher = get_dispatcher()
    try:
        dispatcher.clear_cache(batch.urls)
    except CommunicationError:
        dispatcher = get_dispatcher()
        dispatcher.clear_cache(batch.urls)
    


def start():
    uvicorn.run(app, host=resolve_host(), port=resolve_api_port())
