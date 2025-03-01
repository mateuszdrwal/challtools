from challtools.utils import get_valid_config, build_chall
from challtools.constants import *


def run(args):
    config = get_valid_config()

    if build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")
    else:
        print(f"{BOLD}Nothing to do{CLEAR}")

    return 0
