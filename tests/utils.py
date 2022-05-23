import os
from pathlib import Path
from challtools.cli import main
from challtools.utils import _copytree

testpath = Path(__file__).parent
templatepath = testpath / "templates"
inittemplatepath = testpath / ".." / "challtools" / "templates"


def populate_dir(path: Union[str, Path], template: str) -> None:
    os.chdir(path)

    if not template or not isinstance(template, str):
        raise ValueError("template must be a non-empty string")

    if not (templatepath / template).is_dir():
        raise ValueError("Template not found")

    _copytree(templatepath / template, path)


def main_wrapper(args):
    try:
        exit_code = main(args)
    except SystemExit as e:
        exit_code = e.code

    return exit_code
