import uuid
from pathlib import Path

import yaml

from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.utils import load_ctf_config, process_messages
from challtools.validator import ConfigValidator


def run(args):
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
