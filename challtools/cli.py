import sys
import time
import argparse
from pathlib import Path
import yaml
from .validator import ConfigValidator
from .utils import (
    process_messages,
    load_ctf_config,
    load_config_or_exit,
    get_ctf_config_path,
    get_valid_config_or_exit,
    discover_challenges,
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
    validate_parser.add_argument("-v", "--verbose", action="store_true")
    validate_parser.set_defaults(func=validate)

    validate_all_parser = subparsers.add_parser(
        "validate_all",
        description="Validates all challenges in the CTF to make sure they are defined properly",
    )
    validate_all_parser.add_argument("-v", "--verbose", action="store_true")
    validate_all_parser.set_defaults(func=validate_all)

    build_parser = subparsers.add_parser(
        "build",
        description="Builds a challenge by running its build script and building docker images",
    )
    build_parser.set_defaults(func=build)

    start_parser = subparsers.add_parser(
        "start",
        description="Starts a challenge by running its docker images",
    )
    start_parser.add_argument("-b", "--build", action="store_true")
    start_parser.set_defaults(func=start)

    solve_parser = subparsers.add_parser(
        "solve",
        description="Starts a challenge by running its docker images, and procedes to solve it using the solution container",
    )
    solve_parser.set_defaults(func=solve)

    create_compose_parser = subparsers.add_parser(
        "create_compose",
        description="Writes a docker-compose.yml file to the challenge directory which can be used to run all challenge services",
    )
    create_compose_parser.set_defaults(func=create_compose)

    args = parser.parse_args()

    if not getattr(args, "func", None):
        parser.print_usage()
    else:
        exit(args.func(args))


def validate(args):

    config = load_config_or_exit()

    validator = ConfigValidator(
        config, ctf_config=load_ctf_config(), challdir=Path(".")
    )
    messages = validator.validate()[1]

    processed = process_messages(messages, verbose=args.verbose)

    if processed["highest_level"]:
        print("\n".join(processed["message_strings"]))
    print(processed["count_string"])
    if processed["highest_level"] and not args.verbose:
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

    if args.build and build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")

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


def validate_all(args):

    if get_ctf_config_path() == None:
        print(
            f"{CRITICAL}No CTF configuration file (ctf.yaml) detected in the current directory or any parent directory, and therefore cannot discover challenges.{CLEAR}"
        )
        return 1

    ctf_config = load_ctf_config()

    for path in discover_challenges():
        print(f"{BOLD}Validating {path}{CLEAR}")

        path = path.parent

        config = load_config_or_exit(workdir=path)

        validator = ConfigValidator(config, ctf_config=ctf_config, challdir=path)
        messages = validator.validate()[1]

        processed = process_messages(messages, verbose=args.verbose)

        if processed["highest_level"]:
            print("\n".join(processed["message_strings"]))


def create_compose(args):
    config = get_valid_config_or_exit()

    if config["deployment"]["type"] != "docker":
        print(
            f'{CRITICAL}Only deployments of type "docker" can be used to create a docker-compose file{CLEAR}'
        )
        return 1

    if not config["deployment"]["containers"]:
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

    compose = {
        "version": "3",
        "services": {},
    }

    if config["deployment"]["volumes"]:
        compose["volumes"] = {volume: {} for volume in config["deployment"]["volumes"]}
    if config["deployment"]["networks"]:
        compose["networks"] = {
            network: {} for network in config["deployment"]["networks"]
        }

    next_port = 50000
    used_ports = set()

    # TODO handle services with set external ports first so the auto assigned ports dont potentially conflict with them
    for name, container in config["deployment"]["containers"].items():
        compose_service = {"ports": []}
        volumes = []
        networks = []

        if Path(container["image"]).exists():
            compose_service["build"] = container["image"]
        else:
            compose_service["image"] = container["image"]

        for service in container["services"]:
            external_port = service.get("external_port")
            if not external_port:
                while next_port in used_ports:
                    next_port += 1
                external_port = next_port

            assert external_port not in used_ports
            used_ports.add(external_port)

            compose_service["ports"].append(
                f"{external_port}:{service['internal_port']}"
            )

        for service in container["extra_exposed_ports"]:
            assert service["external_port"] not in used_ports
            used_ports.add(service["external_port"])
            compose_service["ports"].append(
                f"{service['external_port']}:{service['internal_port']}"
            )

        for volume_name, containers in config["deployment"]["volumes"].items():
            for mapping in containers:
                if name in mapping:
                    volumes.append(f"{volume_name}:{mapping[name]}")

        for network_name, containers in config["deployment"]["networks"].items():
            if name in containers:
                networks.append(network_name)

        if volumes:
            compose_service["volumes"] = volumes
        if networks:
            compose_service["networks"] = networks

        compose["services"][name] = compose_service

    Path("docker-compose.yml").write_text(yaml.dump(compose))

    print(f"{SUCCESS}docker-compose.yml written!{CLEAR}")
