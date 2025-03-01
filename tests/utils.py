import os
import shutil
from pathlib import Path
from challtools.entry import main

testpath = Path(__file__).parent
templatepath = testpath / "templates"
inittemplatepath = testpath / ".." / "challtools" / "templates"


def populate_dir(path, template):
    os.chdir(path)

    if not template or not isinstance(template, str):
        raise ValueError("template must be a non-empty string")

    if not (templatepath / template).is_dir():
        raise ValueError("Template not found")

    shutil.copytree(templatepath / template, path, dirs_exist_ok=True)


def main_wrapper(args):
    try:
        exit_code = main(args)
    except SystemExit as e:
        exit_code = e.code

    return exit_code
