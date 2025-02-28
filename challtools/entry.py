# PYTHON_ARGCOMPLETE_OK
import argparse
import inspect
import argcomplete
from challtools import __version__
import challtools.builtins
from challtools.plugin import Plugin
from challtools.exceptions import CriticalException
from challtools.constants import *


def main(passed_args=None):
    parser = argparse.ArgumentParser(
        prog="challtools",
        description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"challtools {__version__}"
    )
    subparsers = parser.add_subparsers(metavar="COMMAND")

    for _, obj in inspect.getmembers(challtools.builtins):
        if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
            obj(parser, subparsers)

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
