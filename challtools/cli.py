import sys
import time
import argparse
from .validator import ConfigValidator
from .utils import (
    process_messages,
    load_config_or_exit,
    get_valid_config_or_exit,
    build_chall,
    start_chall,
    start_solution,
    validate_solution_output,
)
from .constants import *


def main():
    parser = argparse.ArgumentParser(
        prog="challtools",
        description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    )
    subparsers = parser.add_subparsers()

    # TODO add help strings
    validate_parser = subparsers.add_parser(
        "validate",
        description="Validates a challenge to make sure it's defined properly",
    )
    validate_parser.add_argument("-v", action="store_true")
    validate_parser.set_defaults(func=validate)

    build_parser = subparsers.add_parser(
        "build",
        description="Builds a challenge by running its build script and building docker images",
    )
    build_parser.set_defaults(func=build)

    start_parser = subparsers.add_parser(
        "start",
        description="Starts a challenge by running its docker images",
    )
    start_parser.set_defaults(func=start)

    solve_parser = subparsers.add_parser(
        "solve",
        description="Starts a challenge by running its docker images, and procedes to solve it using the solution container",
    )
    solve_parser.set_defaults(func=solve)

    args = parser.parse_args()

    if not getattr(args, "func", None):
        parser.print_usage()
    else:
        exit(args.func(args))


def validate(args):

    config = load_config_or_exit()

    validator = ConfigValidator(config)
    messages = validator.validate()[1]

    processed = process_messages(messages, verbose=args.v)

    if processed["highest_level"]:
        print("\n".join(processed["message_strings"]))
    print(processed["count_string"])
    if processed["highest_level"] and not args.v:
        print("Run with -v for detailed descriptions")

    level_messages = [
        f"{SUCCESS}Validation succeeded. No issues detected!",
        f"{SUCCESS}Validation succeeded.",
        f"{SUCCESS}Validation succeeded.",
        f"{HIGH}Validation succeeded. You may want to investigate some of the issues.",
        f"{HIGH}Validation succeeded, however you should fix errors of high severity.",
        f"{CRITICAL}Validation failed, please fix the critical errors.",
    ]

    print(level_messages[processed["highest_level"]] + CLEAR)
    if processed["highest_level"]:
        return 1

    return 0


def build(args):
    config = get_valid_config_or_exit()

    if build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")
    else:
        print(f"{BOLD}Nothing to do{CLEAR}")

    return 0


def start(args):
    config = get_valid_config_or_exit()

    containers, service_strings = start_chall(config)

    if not containers:
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

    if service_strings:
        print(f"{BOLD}Services:\n" + "\n".join(service_strings) + f"{CLEAR}")

    try:
        for log in containers[0].logs(
            stream=True
        ):  # TODO print logs from all containers, probably stream=False and a for loop iterating over all containers in a while true loop
            sys.stdout.write(log.decode())
    except KeyboardInterrupt:
        print(f"{BOLD}Stopping...{CLEAR}")
        for container in containers:
            container.kill()

    return 0


def solve(args):  # TODO add support for solve script
    config = get_valid_config_or_exit()

    # if not config["solution_image"]:
    #     print(f"{BOLD}No solution defined, cannot solve challenge{CLEAR}")
    #     return 1

    containers, service_strings = start_chall(config)

    if not containers:
        print(f"{BOLD}No services defined, there is nothing to solve{CLEAR}")
        return 1

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
        solution_container.kill()
        solution_container.remove()
        return 1

    solution_container.wait()

    for container in containers:
        container.kill()

    output = solution_container.logs()
    solution_container.remove()

    if validate_solution_output(config, output.decode()):
        print(f"{SUCCESS}Challenge solved successfully!{CLEAR}")
    else:
        print(f"{CRITICAL}Challenge could not be solved{CLEAR}")
        return 1

    return 0