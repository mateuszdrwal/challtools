from challtools.plugin import Plugin


class TestPlugin(Plugin):
    def __init__(self, parser, subparsers):
        validate_parser = subparsers.add_parser(
            "test_command", help="Test plugin command"
        )
        validate_parser.set_defaults(func=run)


def run(args):
    print("hello test plugin")
