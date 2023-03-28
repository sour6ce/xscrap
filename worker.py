import requests

def get_html(url):
    response = requests.get(url)
    html = response.text
    return html
    