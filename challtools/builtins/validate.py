from pathlib import Path

from challtools.constants import *
from challtools.utils import load_config, load_ctf_config, process_messages
from challtools.validator import ConfigValidator


def run(args):

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
