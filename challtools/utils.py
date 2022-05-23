import os
import re
import subprocess
import sys
import hashlib
import json
import shutil
from pathlib import Path
import yaml
import docker
import requests
from .validator import ConfigValidator
from .constants import *


class CriticalException(Exception):
    pass


def process_messages(messages, verbose=False):
    """Processes a list of messages from validator.ConfigValidator.validate for printing.

    Args:
        messages (list): The list of messages returned by validator.ConfigValidator.validate

    Returns:
        dict: Dictionary with the following keys:

            ``message_strings`` (*list*)
                A list of strings containing formatted messages, with ANSI color codes. Example string: ``[CRITICAL] [A002] Schema violation``
            ``count_string`` (*str*)
                A string listing the counts of each message level, with ANSI color codes. Example: ``1 MEDIUM and 1 HIGH issue raised.``
            ``highest_level`` (*int*)
                The highest message level in the message list. Always between 0-5, where 0 is no messages and 5 is CRITICAL.
    """
    level_counts = [0, 0, 0, 0, 0]
    highest_level = 0
    message_strings = []
    for message in messages:
        level_counts[message["level"] - 1] += 1
        highest_level = max(highest_level, message["level"])

        message_string = (
            f"[{STYLED_LEVELS[message['level']-1]}] [{BOLD}{message['code']}{CLEAR}] "
        )
        if message["field"]:
            message_string += f"{message['field']}: "
        message_string += message["name"]
        if verbose:
            message_string += "\n" + message["message"]
        message_strings.append(message_string)

    level_name_counts = {i: count for i, count in enumerate(level_counts) if count}
    count_string = ""

    if level_name_counts:
        count_string += "\n"

    if not level_name_counts:
        count_string += "No"
    else:
        count_string += " and ".join(
            ", ".join(
                f"{count[1]} {STYLED_LEVELS[count[0]]}"
                for count in level_name_counts.items()
            ).rsplit(", ", 1)
        )

    count_string += f" issue{'s' if not level_name_counts or list(level_name_counts.values())[-1] > 1 else ''} raised."

    return {
        "message_strings": message_strings,
        "count_string": count_string,
        "highest_level": highest_level,
    }


def get_ctf_config_path(search_start=Path(".")):
    """Locates the global CTF configuration file (ctf.yml) and returns a path to it.

    Returns:
        pathlib.Path: The path to the config
        None: If there was no CTF config
    """
    p = search_start.absolute()

    for directory in [p, *p.parents]:
        if (directory / "ctf.yml").exists():
            return directory / "ctf.yml"
        if (directory / "ctf.yaml").exists():
            return directory / "ctf.yaml"

    return None


def get_config_path(search_start=Path(".")):
    """Locates the challenge configuration file (challenge.yml) and returns a path to it.

    Returns:
        pathlib.Path: The path to the config
        None: If there was no challenge config
    """
    p = search_start.absolute()

    for directory in [p, *p.parents]:
        if (directory / "challenge.yml").exists():
            return directory / "challenge.yml"
        if (directory / "challenge.yaml").exists():
            return directory / "challenge.yaml"

    return None


def load_ctf_config():
    """Loads the global CTF configuration file (ctf.yml) from the current or a parent directory.

    Returns:
        dict: The config
        None: If there was no CTF config
    """
    ctfpath = get_ctf_config_path()

    if not ctfpath:
        return None

    raw_config = ctfpath.read_text()
    config = yaml.safe_load(raw_config)

    return config if config else {}


def load_config(workdir=".", search=True, cd=True):
    """Loads the challenge configuration file from the current directory, a specified directory, or optionally one of their parent directories. Optionally changes the working directory to the directory of the configuration file.

    Args:
        workdir (string): The directory to search for the configuration file from
        search (bool): If the parent directories of the starting directory should be searched for the configuration file
        cd (bool): If the working directory should be set to the directory the configuration file is found in

    Returns:
        dict: The config

    Raises:
        CriticalException: If the challenge configuration cannot be found
    """

    path = Path(workdir).absolute()

    if search:
        path = get_config_path(path)
    else:
        if (path / "challenge.yml").exists():
            path = path / "challenge.yml"
        elif (path / "challenge.yaml").exists():
            path = path / "challenge.yaml"
        else:
            path = None

    if not path:
        raise CriticalException(
            f"Could not find a challenge.yml file in this{' or a parent' if search else ''} directory."
        )

    raw_config = path.read_text()
    config = yaml.safe_load(raw_config)

    if cd:
        os.chdir(path.parent)

    return config


def get_valid_config(workdir=None, search=True, cd=True):
    """Loads the challenge configuration file from the current directory and makes sure its valid.

    Args:
        workdir (string): The directory to search for the configuration file from
        search (bool): If the parent directories of the starting directory should be searched for the configuration file
        cd (bool): If the working directory should be set to the directory the configuration file is found in

    Returns:
        dict: The normalized config

    Raises:
        CriticalException: If there are critical validation errors
    """
    config = load_config(
        search=search, cd=cd, **{"workdir": workdir} if workdir else {}
    )

    validator = ConfigValidator(config)
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
    elif highest_level == 4:
        print(
            "\n".join(
                process_messages([m for m in messages if m["level"] == 4])[
                    "message_strings"
                ]
            )
        )
        print(
            f"\n{HIGH}There are config validation issues of high severity. You probably want to fix them.{CLEAR}"
        )

    return validator.normalized_config


def discover_challenges(search_start=None):
    """Discovers all challenges at the same level as or in a subdirectory below the CTF configuration file.

    Returns:
        list: A list of pathlib.Path objects to all found challenge configurations
        None: If there was no CTF config
    """
    root = get_ctf_config_path(
        **{"search_start": search_start} if search_start else {}
    ).parent

    if not root:
        return None

    def checkdir(d):
        if (d / "challenge.yml").exists():
            return [d / "challenge.yml"]
        if (d / "challenge.yaml").exists():
            return [d / "challenge.yaml"]
        results = []
        for subd in [f for f in d.iterdir() if f.is_dir()]:
            results += checkdir(subd)
        return results

    return checkdir(root)


def get_docker_client():
    """Gets an authenticated docker client.

    Returns:
        docker.client.DockerClient: The docker client

    Raises:
        CriticalException: If the client cannot be created
    """
    try:
        client = docker.from_env()
        client.images.list()
    except (requests.exceptions.ConnectionError, docker.errors.DockerException) as e:
        lastrow = ""
        if "FileNotFoundError" in e.args[0]:
            lastrow = CRITICAL + "\nIs Docker installed and running?"
        if "PermissionError" in e.args[0]:
            lastrow = CRITICAL + "\nTry running with elevated privelages"
        raise CriticalException(
            f"The following error was recieved when attempting to contact the Docker daemon:\033[22m\n{e.args[0]}"
            + lastrow
        )

    return client


def get_first_text_flag(config):
    """Creates a valid flag with the flag format using the flag format and the first text flag, if it exists.

    Args:
        config (dict): The normalized challenge config

    Returns:
        string: A valid flag.
        None: If there was no text type flag
    """

    text_flag = None
    for flag in config["flags"]:
        if flag["type"] == "text":
            text_flag = flag["flag"]
            break
    else:
        return None

    if not config["flag_format_prefix"]:
        return text_flag

    return config["flag_format_prefix"] + text_flag + config["flag_format_suffix"]


def dockerize_string(string):
    """Converts a string into a valid docker tag name.

    Args:
        string (string): The string to transform

    Returns:
        string: A valid docker tag name.
    """
    string = string.replace(" ", "_")
    string = re.sub(r"[^A-Za-z0-9_.-]", "", string)
    string = string.lstrip("_.-")
    string = string.lower()
    # docker has some fucky-wucky undocumented restriction on not allowing multiple separators in a row. this is (mostly) the same regex as docker engine uses, and it just collapses multiple separators into one
    string = re.sub(r"([._]|__|[-]+){2,}", lambda m: m.group(1), string)
    return string[:128]


def create_docker_name(title, container_name=None, chall_id=None):
    """Converts challenge information into a most likely unique and valid docker tag name.

    Args:
        title (string): The challenge title
        container_name (string): The name of the container whose name this is
        chall_id (string): The challenge_id

    Returns:
        string: A valid docker tag name no longer than 66 characters.
    """
    digest = hashlib.md5(
        (title + "|" + (container_name or "") + "|" + (chall_id or "")).encode()
    ).hexdigest()

    title = dockerize_string(title)

    if container_name:
        container_name = dockerize_string(container_name)
        return "_".join([title[:32], container_name[:16], digest[:16]])

    return "_".join([title[:32], digest[:16]])


def format_user_service(config, service_type, **kwargs):
    """Formats a string displayed to the user based on the service type and a substitution context (``display`` in the OpenChallSpec).

    Args:
        config (dict): The normalized challenge config
        service_type (string): The service type of the service to format
        **kwargs (string): Any substitution context. ``host`` and ``port`` must be provided for the ``tcp`` service type, and ``url`` must be provided for the ``website`` service type however this is not validated.

    Returns:
        string: A formatted string ready to be presented to a CTF player
    """
    service_types = [
        {"type": "website", "display": "{url}"},
        {"type": "tcp", "display": "nc {host} {port}"},
    ] + config["custom_service_types"]
    type_candidate = [i for i in service_types if i["type"] == service_type]

    if not type_candidate:
        raise ValueError(f"Unknown service type {service_type}")
    string = type_candidate[0]["display"]

    for name, value in kwargs.items():
        string = string.replace("{" + name + "}", value)

    return string


def validate_solution_output(config, output):
    """validates a flag outputted by a solver by stripping the whitespace and validating the flag.

    Args:
        config (dict): The normalized challenge config
        output (string): The output from the Solver

    Returns:
        boolean: If the flag was valid
    """
    return validate_flag(config, output.strip())


def validate_flag(config, submitted_flag):
    """validates a flag against the flags in the challenge config.

    Args:
        config (dict): The normalized challenge config
        flag (string): the flag to validate

    Returns:
        boolean: If the flag was valid
    """
    if config["flag_format_prefix"]:
        if not submitted_flag.startswith(
            config["flag_format_prefix"]
        ) or not submitted_flag.endswith(config["flag_format_suffix"]):
            return False
        submitted_flag = submitted_flag[
            len(config["flag_format_prefix"]) : -len(config["flag_format_suffix"])
        ]

    for flag in config["flags"]:
        if flag["type"] == "text":
            if submitted_flag == flag["flag"]:
                return True

        if flag["type"] == "regex":
            if re.search(flag["flag"], submitted_flag):
                return True

    return False


def build_image(image, tag, client):
    """Build a docker image given the image (as a path to a folder, if archive it will load it), the tag and the docker client.

    Args:
        image (string): The image as a path to a folder to build or as a path to an archive to import. if neither, the function won't do anything
        tag (string): The tag name to tag the image as
        client (docker.client.DockerClient): The docker client to use for building

    Raises:
        CriticalException: If the build fails
    """
    imagepath = Path(image)
    if imagepath.is_dir():
        print(
            f'{BOLD}Interpreting "{image}" as an image build directory\nBuilding image...{CLEAR}'
        )
        try:
            stream = client.api.build(
                path=str(imagepath),
                tag=tag,
                rm=True,
            )

            for chunk in stream:
                for line in chunk.strip().split(b"\n"):
                    decoded = json.loads(line)
                    # TODO process progress bars for pulling
                    if "error" in decoded:
                        raise CriticalException(decoded["error"])
                    if "stream" in decoded:
                        print(decoded["stream"], end="")

        except docker.errors.APIError as e:
            raise CriticalException(e.explanation)

    elif imagepath.is_file():
        print(f'{BOLD}Interpreting "{image}" as an image archive{CLEAR}')
        print(f"{BOLD}Importing image...{CLEAR}")
        raise NotImplementedError  # TODO
    else:
        print(
            f'{BOLD}Interpreting "{image}" as an existing image, nothing to build{CLEAR}'
        )


def run_build_script(config):
    if "build_script" not in config["custom"]:
        raise CriticalException(f"Build script has not been defined!")

    print(f"{BOLD}Running build script...{CLEAR}")

    flag = get_first_text_flag(config)

    p = subprocess.Popen(
        [Path(config["custom"]["build_script"]).absolute(), flag],
        stdout=sys.stdout,
        stderr=sys.stdout,
    )
    p.wait()

    if p.returncode != 0:
        raise CriticalException(f"Build script exited with code {p.returncode}")


def build_docker_images(config, client):
    if not config["deployment"]:
        return False

    for container_name, container in config["deployment"]["containers"].items():
        print(f"{BOLD}Processing container {container_name}...{CLEAR}")
        build_image(
            container["image"],
            create_docker_name(
                config["title"],
                container_name=container_name,
                chall_id=config["challenge_id"],
            ),
            client,
        )

    network_list = [network.name for network in client.networks.list()]
    for network_name in config["deployment"]["networks"]:
        if network_name not in network_list:
            print(f"{BOLD}Creating network {network_name}...{CLEAR}")
            client.networks.create(
                network_name
            )  # TODO make network names not collide between challenges, add id hash maybe

    volume_list = [volume.name for volume in client.volumes.list()]
    for volume_name in config["deployment"]["volumes"]:
        if volume_name not in volume_list:
            print(f"{BOLD}Creating volume {volume_name}...{CLEAR}")
            client.volumes.create(
                volume_name
            )  # TODO make volume names not collide between challenges, add id hash maybe

    return True


def build_chall(config):
    """Builds a challenge including running the build script and building service and solution docker images. Expects to be run from the root directory of the challenge.

    Args:
        config (dict): The normalized challenge config

    Returns:
        bool: False if there was nothing to do, True if it ran the build script or built a container

    Raises:
        CriticalException: If the build fails
    """
    did_something = False

    if config["deployment"]:
        if config["deployment"]["type"] != "docker":
            raise CriticalException(
                'challtools only supports the "docker" deployment type'
            )

        client = get_docker_client()

    if "build_script" in config["custom"]:
        did_something = True
        run_build_script(config)

    if config["deployment"]:
        did_something = True
        build_docker_images(config, client)

    if config["solution_image"]:
        did_something = True
        print(f"{BOLD}Processing solution image...{CLEAR}")
        build_image(
            config["solution_image"],
            "sol_"
            + create_docker_name(config["title"], chall_id=config["challenge_id"]),
            client,
        )

    return did_something


def start_chall(config):
    """Starts all docker containers for this challenge.

    Args:
        config (dict): The normalized challenge config

    Returns:
        tuple: The first element is a list of all started containers as docker.models.containers.Container instances. The second element is a list of formatted service strings for displaying to users.

    Raises:
        CriticalException: If the start fails
    """

    if not config["deployment"] or not config["deployment"]["containers"]:
        return [], []

    if config["deployment"]["type"] != "docker":
        raise CriticalException('challtools only supports the "docker" deployment type')

    client = get_docker_client()
    tag_list = [
        tag.split(":")[0]
        for img in client.images.list()
        for tag in img.attrs["RepoTags"]
    ]

    for container_name, container in config["deployment"]["containers"].items():
        tag = create_docker_name(
            config["title"],
            container_name=container_name,
            chall_id=config["challenge_id"],
        )  # TODO check that the container hasn't already been started

        if tag not in tag_list:
            raise CriticalException(
                f'Cannot find image "{tag}". Make sure you have built the required docker images using "challtools build" before attempting to start them.'
            )

    # TODO test that network and volume detection works
    network_list = [network.name for network in client.networks.list()]
    for network_name in config["deployment"]["networks"]:
        if network_name not in network_list:
            raise CriticalException(
                f'Cannot find network "{network_name}". Make sure you have created the required docker networks using "challtools build" before attempting to use them.'
            )

    volume_list = [volume.name for volume in client.volumes.list()]
    for volume_name in config["deployment"]["volumes"]:
        if volume_name not in volume_list:
            raise CriticalException(
                f'Cannot find volume "{volume_name}". Make sure you have created the required docker volumes using "challtools build" before attempting to use them.'
            )

    containers = []
    service_strings = []
    available_port = (
        50000  # TODO add some support for running challenges at the same time
    )

    for container_name, container_config in config["deployment"]["containers"].items():
        tag = create_docker_name(
            config["title"],
            container_name=container_name,
            chall_id=config["challenge_id"],
        )

        ports = {}
        for service in container_config.get("services", []):
            if "external_port" not in service:
                service["external_port"] = available_port
                available_port += 1
            ports[service["internal_port"]] = service["external_port"]

            service_strings.append(
                format_user_service(
                    config,
                    service["type"],
                    host="127.0.0.1",
                    port=str(service["external_port"]),
                    url=f"http://127.0.0.1:{service['external_port']}",
                )
            )

        for extra in container_config.get("extra_exposed_ports", []):
            ports[extra["internal_port"]] = extra["external_port"]

        container = client.containers.create(
            tag,
            ports=ports,
            detach=True,
            environment={"TEST": "true"},
            privileged=container_config["privileged"]
            # TODO volumes
        )

        for network, network_containers in config["deployment"]["networks"].items():
            if container_name in network_containers:
                client.networks.get(network).connect(container)

        container.start()
        print(f"{BOLD}Started container {container_name}{CLEAR}")

        containers.append(container)

    return containers, service_strings


def start_solution(config):
    """Starts a solution container for this challenge.

    Args:
        config (dict): The normalized challenge config

    Returns:
        docker.models.containers.Container: The started docker container

    Raises:
        CriticalException: If the solution cannot be started correctly
    """

    if not config["solution_image"]:
        return None

    client = get_docker_client()
    tag_list = [
        tag.split(":")[0]
        for img in client.images.list()
        for tag in img.attrs["RepoTags"]
    ]
    solution_tag = "sol_" + create_docker_name(
        config["title"], chall_id=config["challenge_id"]
    )

    if solution_tag not in tag_list:
        raise CriticalException(
            f'Cannot find solution image "{solution_tag}". Make sure you have built the required solution docker image using "challtools build" before attempting to start it.'
        )

    service_strings = []
    available_port = 50000

    for predefined_service in config["predefined_services"]:
        service_strings.append(
            format_user_service(config, service["type"], **predefined_service)
        )

    for container_name, container_config in config["deployment"]["containers"].items():
        for service in container_config.get(
            "services", []
        ):  # FIXME validator breaks spec because .get is required, this should always default to an empty array
            if "external_port" not in service:
                service["external_port"] = available_port
                available_port += 1
            service_strings.append(
                format_user_service(
                    config,
                    service["type"],
                    host="127.0.0.1",
                    port=str(service["external_port"]),
                    url=f"http://127.0.0.1:{service['external_port']}",
                )
            )

    container = client.containers.create(
        solution_tag,
        detach=True,
        network="host",
        environment={"TEST": "true"},
        command=service_strings,
    )
    container.start()

    return container


def generate_compose(configs, is_global=False):
    # TODO this whole functions paths are broken, there should be a path argument to generate paths relative to and `is_global` shouldn't exist
    compose = {"version": "3", "services": {}, "volumes": {}, "networks": {}}
    next_port = 50000
    used_ports = set()

    for path, config in configs:
        if not config["deployment"]:
            continue

        if config["deployment"]["type"] != "docker":
            raise CriticalException(
                'Only deployments of type "docker" can be used to create a docker-compose file'
            )

        if config["deployment"]["volumes"]:
            compose["volumes"] = {
                **compose["volumes"],
                **{volume: {} for volume in config["deployment"]["volumes"]},
            }
        if config["deployment"]["networks"]:
            compose["networks"] = {
                **compose["networks"],
                **{network: {} for network in config["deployment"]["networks"]},
            }

        # TODO handle services with set external ports first so the auto assigned ports dont potentially conflict with them
        for name, container in config["deployment"]["containers"].items():
            compose_service = {"ports": []}
            volumes = []
            networks = []

            if is_global:
                image_path = str(
                    (path.parent / container["image"]).relative_to(Path().absolute())
                )
            else:
                image_path = container["image"]
            if Path(image_path).exists():
                compose_service["build"] = image_path
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

            if container["privileged"]:
                compose_service["privileged"] = True

            if is_global:
                compose["services"][
                    create_docker_name(
                        config["title"],
                        container_name=name,
                        chall_id=config["challenge_id"],
                    )
                ] = compose_service
            else:
                compose["services"][name] = compose_service

    if not compose["volumes"]:
        del compose["volumes"]
    if not compose["networks"]:
        del compose["networks"]

    return compose


# https://stackoverflow.com/a/12514470
# needs to exist to support python 3.6 & 3.7, otherwise shutil.copytree should be used with dirs_exist_ok=True
def _copytree(src, dst, ignore=lambda dir, content: list()):
    if not os.path.exists(dst):
        os.makedirs(dst)
    dirlist = os.listdir(src)
    for item in set(dirlist).difference(ignore(src, dirlist)):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            _copytree(s, d, ignore=ignore)
        else:
            shutil.copy(s, d)
