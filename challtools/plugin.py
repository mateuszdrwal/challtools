import argparse
import importlib.util
import sys


class Plugin:
    """
    Base class for all challtools plugins.
    """

    # The priority of the plugin, higher priority plugins are loaded first
    priority: int = 0

    def __init__(
        self, parser: argparse.ArgumentParser, subparsers: argparse._SubParsersAction
    ):
        """
        Initialize the plugin.

        Args:
            parser: The challtools argument parser.
            subparsers: The main command subparsers object that plugins may add their subparsers to.
        """
        raise NotImplementedError("Plugin must implement __init__")


# https://docs.python.org/3/library/importlib.html#implementing-lazy-imports
def lazy_import(name: str):
    """
    Lazy import a module. Always use this function in plugin classes to import
    actual plugin functionality. This minimizes the startup time of challtools
    since imports from commands that aren't ran are never imported.

    Args:
        name: The name of the module to import.

    Returns:
        The imported module.
    """

    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"Module '{name}' not found.")
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def lazy_runner(name: str, func_name: str = "run"):
    """
    Wrapper around lazy_import that returns a module function. When called, this
    function will call the run function of the imported module. This dance is
    done to avoid evaluating the lazy import when accessing the run function.

    Args:
        name: The name of the module to import.
        func_name: The name of the function to call in the imported module.
            Defaults to "run".

    Returns:
        A function that calls the run function of the imported module.
    """

    def run(*args, **kwargs):
        module = lazy_import(name)
        return getattr(module, func_name)(*args, **kwargs)

    return run
