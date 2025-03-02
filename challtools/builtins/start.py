import sys

import docker

from challtools.constants import *
from challtools.utils import build_chall, get_valid_config, start_chall


def run(args):
    config = get_valid_config()

    if args.build and build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")

    containers, service_strings = start_chall(config)

    if not containers:
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

    if len(containers) > 1:
        print(
            f"{HIGH}challtools does not properly support multiple containers yet. All are started, but you will only see information for the first container.{CLEAR}"
        )

    if service_strings:
        print(f"{BOLD}Services:\n" + "\n".join(service_strings) + f"{CLEAR}")

    try:
        for log in containers[0].logs(
            stream=True, stderr=True
        ):  # TODO print logs from all containers
            sys.stdout.write(log.decode())
    except KeyboardInterrupt:
        print(f"{BOLD}Stopping...{CLEAR}")
        for container in containers:
            try:
                container.kill()
            except docker.errors.APIError:
                pass
            try:
                container.remove()
            except docker.errors.APIError:
                pass
        return 0

    for container in containers:
        try:
            container.kill()
        except docker.errors.APIError:
            pass
        try:
            container.remove()
        except docker.errors.APIError:
            pass
    print(f"{HIGH}The container exited by itself.{CLEAR}")
    return 1
