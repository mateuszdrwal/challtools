from pathlib import Path

import yaml

from challtools.constants import *
from challtools.utils import discover_challenges, generate_compose, get_valid_config


def run(args):
    if args.all:
        configs = [
            (path, get_valid_config(path, cd=False)) for path in discover_challenges()
        ]
    else:
        configs = [(Path("."), get_valid_config())]

    compose = generate_compose(configs, args.all, restart_policy=args.restart_policy)

    if not compose["services"]:
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

    Path("compose.yml").write_text(yaml.dump(compose))

    print(f"{SUCCESS}compose.yml written!{CLEAR}")
    return 0
