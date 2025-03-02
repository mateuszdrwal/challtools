import argparse

from challtools import __version__
from challtools.plugin import Plugin, lazy_runner


class Validate(Plugin):
    def __init__(self, parser, subparsers):
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
        validate_parser.set_defaults(func=lazy_runner("challtools.builtins.validate"))


class Init(Plugin):
    def __init__(self, parser, subparsers):
        init_desc = "Initialize a directory with template challenge files"
        init_parser = subparsers.add_parser(
            "init", description=init_desc, help=init_desc
        )
        init_parser.add_argument(
            "template", type=str, default="default", nargs="?"
        ).completer = lazy_runner(
            "challtools.builtins.init", func_name="template_completer"
        )
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
        init_parser.set_defaults(func=lazy_runner("challtools.builtins.init"))


class Build(Plugin):
    def __init__(self, parser, subparsers):
        build_desc = (
            "Builds a challenge by running its build script and building docker images"
        )
        build_parser = subparsers.add_parser(
            "build", description=build_desc, help=build_desc
        )
        build_parser.set_defaults(func=lazy_runner("challtools.builtins.build"))


class Start(Plugin):
    def __init__(self, parser, subparsers):
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
        start_parser.set_defaults(func=lazy_runner("challtools.builtins.start"))


class Solve(Plugin):
    def __init__(self, parser, subparsers):
        solve_desc = "Starts a challenge by running its docker images, and procedes to solve it using the solution container"
        solve_parser = subparsers.add_parser(
            "solve", description=solve_desc, help=solve_desc
        )
        solve_parser.set_defaults(func=lazy_runner("challtools.builtins.solve"))


class Compose(Plugin):
    def __init__(self, parser, subparsers):
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
        compose_parser.add_argument(
            "--restart-policy",
            type=str,
            default="no",
            help="The restart policy to use for all services in the docker-compose file",
        )
        compose_parser.set_defaults(func=lazy_runner("challtools.builtins.compose"))


class EnsureId(Plugin):
    def __init__(self, parser, subparsers):
        ensureid_desc = "Checks if a challenge has a challenge ID, and if not, generates and adds one"
        ensureid_parser = subparsers.add_parser(
            "ensureid", description=ensureid_desc, help=ensureid_desc
        )
        ensureid_parser.set_defaults(func=lazy_runner("challtools.builtins.ensureid"))


class Push(Plugin):
    def __init__(self, parser, subparsers):
        push_desc = "Push a challenge to the ctf platform"
        push_parser = subparsers.add_parser(
            "push", description=push_desc, help=push_desc
        )
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
        push_parser.set_defaults(func=lazy_runner("challtools.builtins.push"))


class SpoilerFree(Plugin):
    def __init__(self, parser, subparsers):
        spoilerfree_desc = "Pretty print challenge information available for participants, for test solving"
        spoilerfree_parser = subparsers.add_parser(
            "spoilerfree", description=spoilerfree_desc, help=spoilerfree_desc
        )
        spoilerfree_parser.set_defaults(
            func=lazy_runner("challtools.builtins.spoilerfree")
        )


class AllChalls(Plugin):
    def __init__(self, parser, subparsers):
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
        allchalls_parser.set_defaults(
            func=lazy_runner("challtools.builtins.allchalls"),
            subparsers=subparsers,
            parser=parser,
        )
