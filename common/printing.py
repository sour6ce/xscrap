from rich.themes import Theme
from rich.console import Console

THEME = Theme({
    "c_good": "green",
    "c_warn": "yellow",
    "c_fail": "bold red",
    "c_logd": "#70a0b0",
    "c_logt": "dim white",
    "c_beauty": "#e0b050",
    "c_iprt": "u"
})

CONSOLE = Console(theme=THEME)
ERR_CONSOLE = Console(stderr=True, theme=THEME)


def print(text: str, style: str = None, **kwargs):
    CONSOLE.print(text, style=style, end='', **kwargs)


def error(text: str, style: str = 'c_fail', **kwargs):
    ERR_CONSOLE.print(text, style=style, end='', **kwargs)


def log(text: str, **kwargs):
    CONSOLE.log(text, **kwargs)
