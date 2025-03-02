from __future__ import annotations
from pathlib import Path
from collections.abc import Callable
from functools import cached_property
from typing import Any, Self, override
import yaml
from challtools.validator import ConfigValidator


class _GeneratedCachedProperty[T]:
    """
    A descriptor that runs a specified function on access. The function is
    expected to overwrite this descriptor on the instance, and it then returns
    the overwritten value. Effectively, this is the equivalent of a
    cached_property where the function computes multiple properties.

    Args:
        func: The function to run on access.
    """

    func: Callable[[T], None]
    name: str = ""

    def __init__(self, func: Callable[[T], None]):
        self.func = func

    def __set_name__(self, owner: T, name: str):
        self.name = name

    def __get__(self, obj: T, objtype: type[T] | None = None) -> Any:
        self.func(obj)
        return getattr(obj, self.name)


class _Challenge:
    config_path: Path  # pyright: ignore [reportUninitializedInstanceVariable] # initialized in __new__

    def __new__(cls, config_path: Path | None = None):
        config_path = config_path.absolute() if config_path else None

        if config_path and not config_path.is_file():
            raise RuntimeError(f"{config_path} is not a file")

        if config_path is None:
            for directory in [context.rundir, *context.rundir.parents]:
                if (directory / "challenge.yaml").exists():
                    config_path = directory / "challenge.yaml"
                    break
                if (directory / "challenge.yml").exists():
                    config_path = directory / "challenge.yml"
                    break
            else:
                return None

        instance = super().__new__(cls)
        instance.config_path = config_path.absolute()
        return instance

    @cached_property
    def raw_config(self) -> dict[str, Any]:
        """The raw parsed configuration file before any validation or normalization is done."""
        data = self.config_path.read_text()
        config = yaml.safe_load(data)

        return config if config else {}

    def _validate(self):
        validator = ConfigValidator(self.raw_config)
        self.valid, self.validator_messages = validator.validate()
        self.normalized_config = validator.normalized_config

    valid: _GeneratedCachedProperty[Self] | bool = _GeneratedCachedProperty(_validate)
    validator_messages: (
        _GeneratedCachedProperty[Self] | list[dict[str, str | int | None]]
    ) = _GeneratedCachedProperty(_validate)
    normalized_config: _GeneratedCachedProperty[Self] | dict[str, Any] = (
        _GeneratedCachedProperty(_validate)
    )

    @override
    def __repr__(self):
        if not self.valid:
            return f"<Challenge at {self.config_path.parent}>"
        return f'<Challenge "{self.normalized_config["title"]}">'


class _CTF:
    config_path: Path  # pyright: ignore [reportUninitializedInstanceVariable] # initialized in __new__

    def __new__(cls):
        for directory in [context.rundir, *context.rundir.parents]:
            if (directory / "ctf.yaml").exists():
                config_path = directory / "ctf.yaml"
                break
            if (directory / "ctf.yml").exists():
                config_path = directory / "ctf.yml"
                break
        else:
            return None

        instance = super().__new__(cls)
        instance.config_path = config_path.absolute()
        return instance

    @cached_property
    def challenges(self):
        """A list of all challenges in the CTF."""
        return [
            _Challenge(p)
            for p in list(self.config_path.parent.glob("**/challenge.yaml"))
            + list(self.config_path.parent.glob("**/challenge.yml"))
        ]

    @cached_property
    def raw_config(self) -> dict[str, Any]:
        """The raw parsed configuration file before any validation or normalization is done."""
        data = self.config_path.read_text()
        config = yaml.safe_load(data)

        return config if config else {}


class _Context:
    rundir: Path = Path.cwd()

    @cached_property
    def challenge(self):
        """The challenge in the current context, if any."""
        return _Challenge()

    @cached_property
    def ctf(self):
        """The CTF in the current context, if any."""
        return _CTF()


context = _Context()
