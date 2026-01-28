import sys
import time

from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.utils import (
    get_valid_config,
    start_chall,
    start_solution,
    validate_solution_output,
)


def run(args):
    config = get_valid_config()

    if not config["solution_image"]:
        print(f"{BOLD}No solution defined, cannot solve challenge{CLEAR}")
        return 0

    containers, service_strings = start_chall(config)

    if not containers:
        print(f"{BOLD}No services defined, there is nothing to solve{CLEAR}")
        return 0

    # sleep to let challenge spin up
    time.sleep(3)
    # TODO if the services have a docker healthcheck, wait for it to pass instead
    # TODO configureable sleep with a cmd arg

    solution_container = start_solution(config)
    print(f"{BOLD}Solving...{CLEAR}")

    try:
        for log in solution_container.logs(stream=True, stderr=True):
            sys.stdout.write(log.decode())
    except KeyboardInterrupt:
        print(f"{BOLD}Aborting...{CLEAR}")
        for container in containers:
            container.kill()
            container.remove()
        solution_container.kill()
        solution_container.remove()
        return 1

    solution_container.wait()

    for container in containers:
        container.kill()
        container.remove()

    output = solution_container.logs()
    solution_container.remove()

    if validate_solution_output(config, output.decode()):
        print(f"{SUCCESS}Challenge solved successfully!{CLEAR}")
    else:
        raise CriticalException("Challenge could not be solved")

    return 0
