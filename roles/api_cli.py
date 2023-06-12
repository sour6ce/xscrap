import requests
from .api import Batch
import json

class start():
    '''
    CLI tool to use the API from the XSCRAP system.

    Commands:
       fetch
       reset
    '''
    def fetch(self,api:str,*urls:str):
        '''
        Given a list of URLs, print for each one a JSON that 
        stores the HTML body and the status code returned. 580 is a special 
        status code for error at DNS or connection start.
        '''
        response:requests.Response = requests.post(f'{api}/fetch', Batch(urls=list(urls)), stream=True)
        for line in response.iter_lines():
            if line:  # filter out keep-alive new lines
                print(line)

    def reset(self,api:str,*urls):
        '''
        Given a list of URLs, clean the result stored in cache from all of 
        them.
        '''
        requests.post(f'{api}/reset', Batch(urls=list(urls)))
    