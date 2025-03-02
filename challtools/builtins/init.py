import importlib.resources
import shutil
import uuid
from pathlib import Path

from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.utils import load_ctf_config


def run(args):
    if args.list:
        for template_path in (
            importlib.resources.files("challtools") / "templates"
        ).iterdir():
            print(
                f"{template_path.name} - {(template_path/'DESCRIPTION').read_text().strip()}"
            )

        return 0

    if any(Path(".").iterdir()) and not args.force:
        raise CriticalException(
            "The current directory is not empty. To proceed anyways, run with -f. This may overwrite some files."
        )

    with importlib.resources.as_file(
        ((importlib.resources.files("challtools") / "templates") / args.template)
    ) as template_dir:
        target_dir = Path(".").absolute()

        if not template_dir.is_dir():
            raise CriticalException(
                f"Could not find template {args.template}. Use -l to list available templates."
            )

        shutil.copytree(
            template_dir,
            target_dir,
            ignore=shutil.ignore_patterns(
                "DESCRIPTION", "challenge.yml", "challenge.yaml"
            ),
            dirs_exist_ok=True,
        )

    if (template_dir / "challenge.yml").is_file():
        target_conf = target_dir / "challenge.yml"
        content = (template_dir / "challenge.yml").read_bytes()

    if (template_dir / "challenge.yaml").is_file():
        target_conf = target_dir / "challenge.yaml"
        content = (template_dir / "challenge.yaml").read_bytes()

    ctf_config = load_ctf_config() or {}

    replacements = {
        b"__ID__": str(uuid.uuid4()).encode(),
        b"__FLAG_FORMAT_PREFIX__": ctf_config.get("flag_format_prefixes", ["CTF{"])[
            0
        ].encode(),
    }

    for marker, replacement in replacements.items():
        content = content.replace(marker, replacement)

    target_conf.write_bytes(content)

    print(f"{SUCCESS}Directory initialized!{CLEAR}")
    return 0


def template_completer(**kwargs):
    return [
        path.name
        for path in (importlib.resources.files("challtools") / "templates").iterdir()
    ]
