import sys
import time
import argparse
import os
import uuid
import hashlib
from pathlib import Path
import requests
import yaml
from google.cloud import storage

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
    format_user_service,
)
from .constants import *


def main():
    parser = argparse.ArgumentParser(
        prog="challtools",
        description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    )
    subparsers = parser.add_subparsers()

    # TODO add help strings
    allchalls_parser = subparsers.add_parser(
        "allchalls",
        description="Runs a different command on every challenge in this ctf",
    )
    allchalls_parser.add_argument("command", nargs=argparse.REMAINDER)
    allchalls_parser.add_argument("-e", "--exit-on-failure", action="store_true")
    allchalls_parser.set_defaults(func=allchalls, subparsers=subparsers, parser=parser)

    validate_parser = subparsers.add_parser(
        "validate",
        description="Validates a challenge to make sure it's defined properly",
    )
    validate_parser.add_argument("-v", "--verbose", action="store_true")
    validate_parser.add_argument(
        "-e",
        "--error-level",
        type=int,
        default=5,
        help="If a validation message with this level or above is raised, the command exits with exit code 1",
    )
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
    start_parser.add_argument("-b", "--build", action="store_true")
    start_parser.set_defaults(func=start)

    solve_parser = subparsers.add_parser(
        "solve",
        description="Starts a challenge by running its docker images, and procedes to solve it using the solution container",
    )
    solve_parser.set_defaults(func=solve)

    compose_parser = subparsers.add_parser(
        "compose",
        description="Writes a docker-compose.yml file to the challenge directory which can be used to run all challenge services",
    )
    compose_parser.set_defaults(func=compose)

    ensureid_parser = subparsers.add_parser(
        "ensureid",
        description="Checks if a challenge has a challenge ID, and if not, generates and adds one",
    )
    ensureid_parser.set_defaults(func=ensureid)

    push_parser = subparsers.add_parser(
        "push",
        description="Push a challenge to the ctf platform",
    )
    push_parser.set_defaults(func=push)

    args = parser.parse_args()

    if not getattr(args, "func", None):
        parser.print_usage()
    else:
        exit(args.func(args))


def allchalls(args):
    parser = args.subparsers.choices.get(args.command[0])

    if not parser:
        print(
            f"{CRITICAL}Allchalls could not find the specified command to run on all challenges. Run {args.parser.prog} -h to view all commands.{CLEAR}"
        )
        return 1

    if get_ctf_config_path() == None:
        print(
            f"{CRITICAL}No CTF configuration file (ctf.yml) detected in the current directory or any parent directory, and therefore cannot discover challenges.{CLEAR}"
        )
        return 1

    parser_args = parser.parse_args(args.command[1:])
    failed = False
    for path in discover_challenges():
        print(f"{BOLD}Running {args.command[0]} on {path}{CLEAR}")
        os.chdir(path.parent)

        try:
            exit_code = parser_args.func(parser_args)
        except SystemExit as e:
            exit_code = e.code or 0

        if exit_code:
            failed = True
            if args.exit_on_failure:
                return 1

    return int(failed)


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

    status = "failed" if processed["highest_level"] >= args.error_level else "succeeded"
    level_intro_colors = [
        SUCCESS,
        SUCCESS,
        SUCCESS,
        HIGH,
        HIGH,
        CRITICAL,
    ]
    color = level_intro_colors[processed["highest_level"]]
    if processed["highest_level"] >= args.error_level:
        color = CRITICAL

    level_messages = [
        "No issues detected!",
        "",
        "",
        "You may want to investigate some of the issues.",
        "You should fix errors of high severity.",
        "Please fix the critical errors.",
    ]

    print(
        f"{color}Validation {status}. "
        + level_messages[processed["highest_level"]]
        + CLEAR
    )
    if processed["highest_level"] >= args.error_level:
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


def compose(args):
    config = get_valid_config_or_exit()

    if not config["deployment"] or not config["deployment"].get("containers"):
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

    if config["deployment"]["type"] != "docker":
        print(
            f'{CRITICAL}Only deployments of type "docker" can be used to create a docker-compose file{CLEAR}'
        )
        return 1

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
    return 0


def ensureid(args):
    path = Path(".")
    if (path / "challenge.yml").exists():
        path = path / "challenge.yml"
    elif (path / "challenge.yaml").exists():
        path = path / "challenge.yaml"
    else:
        print(
            f"{CRITICAL}Could not find a challenge.yml file in this directory.{CLEAR}"
        )
        return 1

    with path.open() as f:
        raw_config = f.read()
    config = yaml.safe_load(raw_config)

    validator = ConfigValidator(
        config, ctf_config=load_ctf_config(), challdir=Path(".")
    )
    messages = validator.validate()[1]
    highest_level = process_messages(messages)["highest_level"]
    if highest_level == 5:
        print(
            "\n".join(
                process_messages([m for m in messages if m["level"] == 5])[
                    "message_strings"
                ]
            )
        )
        print(
            f"\n{CRITICAL}There are critical config validation errors. Please fix them before continuing."
        )
        return 1
    config = validator.normalized_config

    if config["challenge_id"]:
        print(f"{SUCCESS}Challenge ID present!{CLEAR}")
        return 0

    if raw_config.endswith("\n\n"):
        pass
    elif raw_config.endswith("\n"):
        raw_config += "\n"
    else:
        raw_config += "\n\n"

    raw_config += f"challenge_id: {uuid.uuid4()}\n"

    try:
        edited_config = yaml.safe_load(raw_config)
        del edited_config["challenge_id"]
        validator = ConfigValidator(
            edited_config, ctf_config=load_ctf_config(), challdir=Path(".")
        )
        messages = validator.validate()[1]
        assert process_messages(messages)["highest_level"] != 5
        assert validator.normalized_config == config
    except (yaml.reader.ReaderError, KeyError, AssertionError):
        print(
            f"{CRITICAL}Could not automatically add the ID to the config. Here is a random ID for you to add manually: {uuid.uuid4()}{CLEAR}"
        )
        return 1

    path.write_text(raw_config)
    print(f"{SUCCESS}Challenge ID written to config!{CLEAR}")
    return 0


def push(args):
    config = get_valid_config_or_exit()
    ctf_config = load_ctf_config()

    if not config["challenge_id"]:
        print(f"{CRITICAL}ID not configured in the challenge configuration file{CLEAR}")
        return 1

    if not ctf_config.get("custom", {}).get("platform_url"):
        print(
            f"{CRITICAL}Platform URL not configured in the CTF configuration file{CLEAR}"
        )
        return 1

    if not ctf_config.get("custom", {}).get("platform_api_key"):
        print(
            f"{CRITICAL}Platform API key not configured in the CTF configuration file{CLEAR}"
        )
        return 1

    file_urls = []

    if not config["downloadable_files"]:
        print(f"{BOLD}No files defined, nothing to upload{CLEAR}")
    else:

        if not ctf_config.get("custom", {}).get("bucket"):
            print(
                f"{CRITICAL}Bucket not configured in the CTF configuration file{CLEAR}"
            )
            return 1

        if not ctf_config.get("custom", {}).get("secret"):
            print(
                f"{CRITICAL}Secret not configured in the CTF configuration file{CLEAR}"
            )
            return 1

        storage_client = storage.Client()
        bucket = storage_client.bucket(ctf_config["custom"]["bucket"])
        folder = hashlib.sha256(
            f"{ctf_config['custom']['secret']}-{config['challenge_id']}".encode()
        ).hexdigest()

        for blob in bucket.list_blobs(prefix=folder):
            print(f"{BOLD}Deleting old {blob.name.split('/')[-1]}...{CLEAR}")
            blob.delete()

        filepaths = []
        for file in config["downloadable_files"]:
            path = Path(file)
            if path.is_dir():
                filepaths += list(path.iterdir())
            else:
                filepaths.append(path)

        for path in filepaths:
            if not path.exists():
                print(f"{CRITICAL}file {path} does not exist!{CLEAR}")

            print(f"{BOLD}Uploading {path.name}...{CLEAR}")
            blob = bucket.blob(folder + "/" + path.name)
            blob.upload_from_file(path.open("rb"))
            file_urls.append(blob.public_url)

    service_types = {
        s["type"]: s
        for s in [
            {"type": "website", "user_display": "{url}", "hyperlink": True},
            {"type": "tcp", "user_display": "nc {host} {port}", "hyperlink": False},
        ]
        + config["custom_service_types"]
    }

    payload = {
        "title": config["title"],
        "description": config["description"],
        "authors": config["authors"],
        "categories": config["categories"],
        "score": config["score"],
        "challenge_id": config["challenge_id"],
        "flag_format_prefix": config["flag_format_prefix"],
        "flag_format_suffix": config["flag_format_suffix"],
        "file_urls": file_urls,
        "flags": config["flags"],
        "order": config["custom"].get("order"),
        "services": [
            {
                "hyperlink": service_types[c["type"]]["hyperlink"],
                "user_display": format_user_service(config, c["type"], **c),
            }
            for c in config["predefined_services"]
        ],
    }

    r = requests.post(
        ctf_config["custom"]["platform_url"] + "/api/admin/push_challenge",
        json=payload,
        headers={"X-API-Key": ctf_config["custom"]["platform_api_key"]},
    )

    if r.status_code != 200:
        print(f"{CRITICAL}Request failed with status {r.status_code}{CLEAR}")
        return 1

    print(f"{SUCCESS}Challenge pushed!{CLEAR}")
    return 0
