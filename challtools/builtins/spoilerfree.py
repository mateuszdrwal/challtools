from challtools.utils import get_valid_config, format_user_service
from challtools.constants import *


def run(args):
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
