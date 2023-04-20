import re

dom_re = re.compile(r"(?<=//)[^/]+(?=/)")


def get_domain(url: str):
    return dom_re.findall(url)[0]
