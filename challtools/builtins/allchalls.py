import os

from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.utils import discover_challenges, get_ctf_config_path


def run(args):
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
