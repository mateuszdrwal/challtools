# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import importlib.util
import inspect
from collections import defaultdict
from pathlib import Path

import argcomplete

import challtools.builtins
from challtools import __version__
from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.plugin import Plugin


def main(passed_args: list[str] | None = None):
    """Main entry point for the challtools CLI."""
    parser = argparse.ArgumentParser(
        prog="challtools",
        description="A tool for managing CTF challenges and challenge repositories using the OpenChallSpec",
    )
    subparsers = parser.add_subparsers(metavar="COMMAND")

    plugin_modules = [challtools.builtins]

    # discover plugins in parent directories
    curpath = Path().absolute()
    for directory in [curpath, *curpath.parents]:
        plugins_dir = directory / ".challtools/plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir():
                    spec = importlib.util.spec_from_file_location(
                        plugin_dir.name, (plugin_dir / "__init__.py").absolute()
                    )
                    if spec is None or spec.loader is None:
                        print(
                            f"{HIGH}Could not load plugin {plugin_dir}, skipping{CLEAR}"
                        )
                        continue
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)
                    plugin_modules.append(plugin_module)
            break

    plugin_classes: list[type[Plugin]] = []

    for plugin_module in plugin_modules:
        for _, obj in inspect.getmembers(plugin_module):
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                plugin_classes.append(obj)

    plugin_classes.sort(key=lambda p: p.priority)
    for plugin_class in plugin_classes:
        _ = plugin_class(parser, subparsers)

    _ = parser.add_argument("-v", "--version", action="store_true")

    argcomplete.autocomplete(parser, always_complete_options=False)

    args = parser.parse_args(passed_args)

    if args.version:
        print(f"challtools {__version__}\n")

        plugin_classes_by_module: defaultdict[str, list[str]] = defaultdict(list)
        for plugin_class in plugin_classes:
            plugin_classes_by_module[plugin_class.__module__].append(
                plugin_class.__name__
            )

        print("Plugins:")
        for plugin_module in plugin_modules:
            version = getattr(plugin_module, "__version__", "unknown version")
            print(
                f"  {plugin_module.__name__} {version} ({', '.join(plugin_classes_by_module[plugin_module.__name__])})"
            )
        exit()

    if not getattr(args, "func", None):
        parser.print_usage()
    else:
        try:
            exit(args.func(args))
        except CriticalException as e:
            print(CRITICAL + e.args[0] + CLEAR)
            exit(1)
