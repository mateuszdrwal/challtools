from challtools.constants import *
from challtools.utils import build_chall, get_valid_config


def run(args):
    config = get_valid_config()

    if build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")
    else:
        print(f"{BOLD}Nothing to do{CLEAR}")

    return 0
