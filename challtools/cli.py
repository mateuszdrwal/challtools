# PYTHON_ARGCOMPLETE_OK
import sys
import time
import argparse
import os
import uuid
import hashlib
import shutil
import urllib.parse
import json
from pathlib import Path
import pkg_resources
import requests
import yaml
import docker
import argcomplete
from .validator import ConfigValidator
from .utils import (
    CriticalException,
    process_messages,
    load_ctf_config,
    load_config,
    get_ctf_config_path,
    get_valid_config,
    discover_challenges,
    get_docker_client,
    create_docker_name,
    build_docker_images,
    build_chall,
    start_chall,
    start_solution,
    validate_solution_output,
    format_user_service,
    generate_compose,
    _copytree,
)
from .constants import *


def main(passed_args=None):
    parser = argparse.ArgumentParser(
        prog="challtools",
        description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    )
    subparsers = parser.add_subparsers(metavar="COMMAND")

    allchalls_desc = "Runs a different command on every challenge in this ctf"
    allchalls_parser = subparsers.add_parser(
        "allchalls", description=allchalls_desc, help=allchalls_desc
    )
    allchalls_parser.add_argument("command", nargs=argparse.REMAINDER)
    allchalls_parser.add_argument(
        "-e",
        "--exit-on-failure",
        action="store_true",
        help="Exit as soon as the command fails on any challenge",
    )
    allchalls_parser.set_defaults(func=allchalls, subparsers=subparsers, parser=parser)

    validate_desc = "Validates a challenge to make sure it's defined properly"
    validate_parser = subparsers.add_parser(
        "validate", description=validate_desc, help=validate_desc
    )
    validate_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show message details"
    )
    validate_parser.add_argument(
        "-e",
        "--error-level",
        type=int,
        default=5,
        help="If a validation message with this level or above is raised, the command exits with exit code 1",
    )
    validate_parser.set_defaults(func=validate)

    build_desc = (
        "Builds a challenge by running its build script and building docker images"
    )
    build_parser = subparsers.add_parser(
        "build", description=build_desc, help=build_desc
    )
    build_parser.set_defaults(func=build)

    start_desc = "Starts a challenge by running its docker images"
    start_parser = subparsers.add_parser(
        "start", description=start_desc, help=start_desc
    )
    start_parser.add_argument(
        "-b",
        "--build",
        action="store_true",
        help="Rebuild the challenge before starting",
    )
    start_parser.set_defaults(func=start)

    solve_desc = "Starts a challenge by running its docker images, and procedes to solve it using the solution container"
    solve_parser = subparsers.add_parser(
        "solve", description=solve_desc, help=solve_desc
    )
    solve_parser.set_defaults(func=solve)

    compose_desc = "Writes a docker-compose.yml file to the challenge directory which can be used to run all challenge services"
    compose_parser = subparsers.add_parser(
        "compose", description=compose_desc, help=compose_desc
    )
    compose_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Write a single docker-compose.yml for all challenges in the CTF",
    )
    compose_parser.set_defaults(func=compose)

    ensureid_desc = (
        "Checks if a challenge has a challenge ID, and if not, generates and adds one"
    )
    ensureid_parser = subparsers.add_parser(
        "ensureid", description=ensureid_desc, help=ensureid_desc
    )
    ensureid_parser.set_defaults(func=ensureid)

    push_desc = "Push a challenge to the ctf platform"
    push_parser = subparsers.add_parser("push", description=push_desc, help=push_desc)
    push_parser.add_argument(
        "--skip-files",
        action="store_true",
        help="Do not upload downloadable files anywhere",
    )
    push_parser.add_argument(
        "--skip-container-build",
        action="store_true",
        help="Do not build challenge containers before pushing",
    )
    push_parser.add_argument(
        "--skip-container-push",
        action="store_true",
        help="Do not build or push containers to any registry",
    )
    push_parser.set_defaults(func=push)

    init_desc = "Initialize a directory with template challenge files"
    init_parser = subparsers.add_parser("init", description=init_desc, help=init_desc)
    init_parser.add_argument(
        "template", type=str, default="default", nargs="?"
    ).completer = templateCompleter
    init_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force initialization even if the directory is not empty",
    )
    init_parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List existing templates",
    )
    init_parser.set_defaults(func=init)

    spoilerfree_desc = "Pretty print challenge information available for participants, for test solving"
    spoilerfree_parser = subparsers.add_parser(
        "spoilerfree", description=spoilerfree_desc, help=spoilerfree_desc
    )
    spoilerfree_parser.set_defaults(func=spoilerfree)

    argcomplete.autocomplete(parser, always_complete_options=False)

    args = parser.parse_args(passed_args)

    if not getattr(args, "func", None):
        parser.print_usage()
    else:
        try:
            exit(args.func(args))
        except CriticalException as e:
            print(CRITICAL + e.args[0] + CLEAR)
            exit(1)


def allchalls(args):
    parser = args.subparsers.choices.get(args.command[0])

    if not parser:
        raise CriticalException(
            f"Allchalls could not find the specified command to run on all challenges. Run {args.parser.prog} -h to view all commands."
        )

    if get_ctf_config_path() == None:
        raise CriticalException(
            "No CTF configuration file (ctf.yml) detected in the current directory or any parent directory, and therefore cannot discover challenges."
        )

    parser_args = parser.parse_args(args.command[1:])
    failed = False
    for path in discover_challenges():
        print(f"{BOLD}Running {args.command[0]} on {path}{CLEAR}")
        os.chdir(path.parent)

        try:
            exit_code = parser_args.func(parser_args)
        except CriticalException as e:
            print(CRITICAL + e.args[0] + CLEAR)
            exit_code = 1

        if exit_code:
            failed = True
            if args.exit_on_failure:
                return 1

    return int(failed)


def validate(args):

    config = load_config()

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
    config = get_valid_config()

    if build_chall(config):
        print(f"{SUCCESS}Challenge built successfully!{CLEAR}")
    else:
        print(f"{BOLD}Nothing to do{CLEAR}")

    return 0


def start(args):
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
        ):  # TODO print logs from all containers, probably stream=False and a for loop iterating over all containers in a while true loop
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


def solve(args):  # TODO add support for solve script
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
        raise CriticalException("Challenge could not be solved")

    return 0


def compose(args):
    if args.all:
        configs = [(path, get_valid_config(path)) for path in discover_challenges()]
    else:
        configs = [(Path("."), get_valid_config())]

    compose = generate_compose(configs, args.all)

    if not compose["services"]:
        print(f"{BOLD}No services defined, nothing to do{CLEAR}")
        return 0

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
        raise CriticalException(
            "Could not find a challenge.yml file in this directory."
        )

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
        print()
        raise CriticalException(
            "There are critical config validation errors. Please fix them before continuing."
        )

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
        raise CriticalException(
            f"Could not automatically add the ID to the config. Here is a random ID for you to add manually: {uuid.uuid4()}"
        )

    path.write_text(raw_config)
    print(f"{SUCCESS}Challenge ID written to config!{CLEAR}")
    return 0


def push(args):
    config = get_valid_config()
    ctf_config = load_ctf_config()

    if not config["challenge_id"]:
        raise CriticalException("ID not configured in the challenge configuration file")

    if not ctf_config.get("custom", {}).get("platform_url"):
        raise CriticalException(
            "Platform URL not configured in the CTF configuration file"
        )

    if not ctf_config.get("custom", {}).get("platform_api_key"):
        raise CriticalException(
            "Platform API key not configured in the CTF configuration file"
        )

    file_urls = [file for file in config["downloadable_files"] if is_url(file)]

    if not args.skip_container_build and not args.skip_container_push:
        if build_docker_images(config, get_docker_client()):
            print(f"{BOLD}Challenge built{CLEAR}")
        else:
            print(f"{BOLD}Nothing to build{CLEAR}")

    if not args.skip_files:
        try:
            from google.cloud import storage
        except ImportError:
            raise CriticalException("google-cloud-storage is not installed!")

        if not config["downloadable_files"]:
            print(f"{BOLD}No files defined, nothing to upload{CLEAR}")
        else:

            if not ctf_config.get("custom", {}).get("bucket"):
                raise CriticalException(
                    "Bucket not configured in the CTF configuration file"
                )

            if not ctf_config.get("custom", {}).get("secret"):
                raise CriticalException(
                    "Secret not configured in the CTF configuration file"
                )

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
                if is_url(file):
                    continue

                path = Path(file)
                if path.is_dir():
                    filepaths += list(path.iterdir())
                else:
                    filepaths.append(path)

            for path in filepaths:
                if not path.exists():
                    raise CriticalException(f"file {path} does not exist!")

                print(f"{BOLD}Uploading {path.name}...{CLEAR}")
                blob = bucket.blob(folder + "/" + path.name)
                blob.upload_from_file(path.open("rb"))
                file_urls.append(blob.public_url)

    if not args.skip_container_push and config["deployment"]:
        try:
            import google.auth
            import google.auth.transport.requests
        except ImportError:
            raise CriticalException("google.auth could not be imported!")

        if not ctf_config.get("custom", {}).get("container_registry"):
            raise CriticalException(
                "Docker registry has not been configured in the CTF configuration file"
            )

        print(f"{BOLD}Authenticating with registry...{CLEAR}")

        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        if not creds.valid:
            raise CriticalException("Could not authenticate with GCP")

        client = get_docker_client()
        r = client.login(
            "oauth2accesstoken",
            creds.token,
            registry=ctf_config["custom"]["container_registry"],
            reauth=True,
        )
        if not r.get("Status", "") == "Login Succeeded":
            raise CriticalException("Could not login with docker")

        for container_name, _ in config["deployment"]["containers"].items():
            container_name = create_docker_name(
                config["title"],
                container_name=container_name,
                chall_id=config["challenge_id"],
            )
            repo_container_name = urllib.parse.urljoin(
                ctf_config["custom"]["container_registry"], container_name
            )

            print(f"{BOLD}Pushing container {container_name}...{CLEAR}")
            client.images.get(container_name).tag(repo_container_name)
            stream = client.images.push(repo_container_name, stream=True)
            for log in stream:
                log = json.loads(log)
                if "error" in log:
                    raise CriticalException(
                        f"{CRITICAL}Failed pushing the container to the repository:{CLEAR}\n\033[31m{log['error']}"
                    )

    service_types = {
        s["type"]: s
        for s in [
            {"type": "website", "display": "{url}", "hyperlink": True},
            {"type": "tcp", "display": "nc {host} {port}", "hyperlink": False},
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

    print(f"{BOLD}Pushing to platform...{CLEAR}")

    r = requests.post(
        ctf_config["custom"]["platform_url"] + "/api/admin/push_challenge",
        json=payload,
        headers={"X-API-Key": ctf_config["custom"]["platform_api_key"]},
    )

    if r.status_code != 200:
        raise CriticalException(f"Request failed with status {r.status_code}")

    print(f"{SUCCESS}Challenge pushed!{CLEAR}")
    return 0


def init(args):

    if args.list:
        for template_path in Path(
            pkg_resources.resource_filename("challtools", "templates")
        ).iterdir():
            print(
                f"{template_path.name} - {(template_path/'DESCRIPTION').read_text().strip()}"
            )

        return 0

    if any(Path(".").iterdir()) and not args.force:
        raise CriticalException(
            "The current directory is not empty. To proceed anyways, run with -f. This may overwrite some files."
        )

    template_dir = (
        Path(pkg_resources.resource_filename("challtools", "templates")) / args.template
    )
    target_dir = Path(".").absolute()
    if not template_dir.is_dir():
        raise CriticalException(
            f"Could not find template {args.template}. Use -l to list available templates."
        )

    _copytree(
        template_dir,
        target_dir,
        ignore=shutil.ignore_patterns("DESCRIPTION", "challenge.yml", "challenge.yaml"),
    )

    if (template_dir / "challenge.yml").is_file():
        target_conf = target_dir / "challenge.yml"
        content = (template_dir / "challenge.yml").read_bytes()

    if (template_dir / "challenge.yaml").is_file():
        target_conf = target_dir / "challenge.yaml"
        content = (template_dir / "challenge.yaml").read_bytes()

    ctf_config = load_ctf_config() or {}

    replacements = {
        b"__ID__": str(uuid.uuid4()).encode(),
        b"__FLAG_FORMAT_PREFIX__": ctf_config.get("flag_format_prefixes", ["CTF{"])[
            0
        ].encode(),
    }

    for marker, replacement in replacements.items():
        content = content.replace(marker, replacement)

    target_conf.write_bytes(content)

    print(f"{SUCCESS}Directory initialized!{CLEAR}")
    return 0


def templateCompleter(**kwargs):
    return [
        path.name
        for path in Path(
            pkg_resources.resource_filename("challtools", "templates")
        ).iterdir()
    ]


def spoilerfree(args):
    config = get_valid_config()

    print(f"\033[1;97m{config['title']}{CLEAR}")
    print(config["description"])
    print()
    print(f"{BOLD}Created by:")
    print("\n".join(f"{BOLD}- \033[1;94m{a}{CLEAR}" for a in config["authors"]))
    print()
    print(f"{BOLD}Categories:")
    print("\n".join(f"{BOLD}- \033[1;94m{c}{CLEAR}" for c in config["categories"]))

    if config["hints"]:
        print()
        print(f"{BOLD}Hints:")
        print("\n".join(f"{BOLD}- {CLEAR}" + h["content"] for h in config["hints"]))

    if config["flag_format_prefix"] is None:
        print()
        print(f"\033[1;94mFlag does not include the flag format!{CLEAR}")
    else:
        print()
        print(
            f"{BOLD}Flag format: \033[1;94m{config['flag_format_prefix']}...{config['flag_format_suffix']}{CLEAR}"
        )

    if config["score"]:
        print()
        print(f"{BOLD}Score: \033[1;94m{config['score']}{CLEAR}")

    if config["downloadable_files"]:
        print()
        print(f"{BOLD}Files:")
        print(
            "\n".join(
                f"{BOLD}- \033[1;94m{f}{CLEAR}" for f in config["downloadable_files"]
            )
        )

    if config["deployment"] or config["predefined_services"]:
        print()
        print(f"{BOLD}Services:")
        if config["deployment"]:
            print(
                "\n".join(
                    f"{BOLD}- \033[1;94m{s['type']} service{CLEAR}"
                    for c in config["deployment"]["containers"].values()
                    for s in c["services"]
                )
            )
        print(
            "\n".join(
                f"{BOLD}- \033[1;94m{format_user_service(config, s['type'], **s)}{CLEAR}"
                for s in config["predefined_services"]
            )
        )

    return 0
