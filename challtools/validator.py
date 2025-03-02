from __future__ import annotations

import importlib.resources
import json
import re
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft7Validator, ValidationError, validate, validators
from jsonschema.protocols import Validator

from challtools.types import (
    JsonDict,
    ValidatorMessage,
)

with (importlib.resources.files("challtools") / "codes.yml").open() as f:
    codes = yaml.safe_load(f)

with (importlib.resources.files("challtools") / "challenge.schema.json").open() as f:
    schema = json.load(f)


def is_url(s: str):
    """Checks if a string is a http or https URL."""
    return s.startswith("http://") or s.startswith("https://")


def _extend_with_default(validator_class: type[Draft7Validator]) -> type[Validator]:
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(
        validator: Validator,
        properties: dict[str, JsonDict],
        instance: JsonDict | None,
        schema2: dict[str, JsonDict],
    ) -> Generator[ValidationError, Any, None]:
        if instance is not None:
            for property2, subschema in properties.items():
                if "default" in subschema:
                    _ = instance.setdefault(property2, subschema["default"])

        yield from validate_properties(
            validator,
            properties,
            instance,
            schema2,
        )

    return validators.extend(  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingDraft7Validator = _extend_with_default(Draft7Validator)


class ConfigValidator:
    """A class to validate challenge configurations."""

    def __init__(
        self,
        config: JsonDict,
        ctf_config: JsonDict | None = None,
        challdir: Path | None = None,
    ):
        self.messages: list[ValidatorMessage] = []
        self.normalized_config: JsonDict | None = None
        self.config: JsonDict = config
        self.ctf_config: JsonDict | None = ctf_config
        self.challdir: Path | None = challdir

    def validate(self) -> tuple[bool, list[ValidatorMessage]]:
        """Validates the challenge config and returns a list of messages.

        Returns:
            tuple: First item is a bool denoting if the config is valid or not. The second item is an array of messages which are dicts formatted thusly:

                ``code`` (*str*)
                    The message code
                ``field`` (*str, None*)
                    The name of the field this message is associated with, if it exists
                ``name`` (*str*)
                    The name of this message
                ``level`` (*int*)
                    The level of the message, where 1 is lowest and 5 is highest. Any message at level 5 will cause the config to be invalid.
                ``message`` (*str*)
                    A longer description of this message
        """

        # TODO A001

        # A002, validating schema
        try:
            validate(instance=self.config, schema=schema)
        except ValidationError as e:
            path = ""
            if e.absolute_path:
                for part in e.absolute_path:
                    if isinstance(part, int):
                        path += f"[{part}]."
                        continue
                    path += part + "."
                path = path[:-1]
            else:
                path = "root"

            self._raise_code(
                "A002",
                path,
                message=e.message,
            )
            return (
                False,
                self.messages,
            )  # stop validation here in case of schema violations

        ### normalizing config
        self.normalized_config = deepcopy(self.config)
        # insterting defaults
        DefaultValidatingDraft7Validator(schema).validate(self.normalized_config)
        # converting strings that should be lists into lists
        for field in [
            "authors",
            "categories",
            "tags",
            "downloadable_files",
            "unlocked_by",
        ]:
            if isinstance(self.normalized_config[field], str):
                self.normalized_config[field] = [self.normalized_config[field]]
        # expanding the simple single flag string format
        if isinstance(self.normalized_config["flags"], str):
            self.normalized_config["flags"] = [
                {"flag": self.normalized_config["flags"], "type": "text"}
            ]
        # converting port in tcp predefined services to string
        for predefined_service in self.normalized_config["predefined_services"]:
            if predefined_service["type"] == "tcp" and isinstance(
                predefined_service["port"], int
            ):
                predefined_service["port"] = str(predefined_service["port"])
        # convert service into deployment
        if self.normalized_config["service"]:
            self.normalized_config["deployment"] = cast(
                JsonDict,
                {
                    "type": "docker",
                    "containers": {
                        "challenge": {  # TODO change the name of this container to "default" in the spec and here
                            "image": self.normalized_config["service"]["image"],
                            "services": [
                                {
                                    "type": self.normalized_config["service"]["type"],
                                    "internal_port": self.normalized_config["service"][
                                        "internal_port"
                                    ],
                                }
                            ],
                            "extra_exposed_ports": [],
                            "privileged": self.normalized_config["service"][
                                "privileged"
                            ],
                        },
                    },
                    "networks": {},
                    "volumes": {},
                },
            )
            if self.normalized_config["service"].get("external_port"):
                self.normalized_config["deployment"]["containers"]["challenge"][
                    "services"
                ][0]["external_port"] = self.normalized_config["service"][
                    "external_port"
                ]
            self.normalized_config["service"] = None
        # normalization done

        # A003
        if self.challdir:
            for file in self.normalized_config["downloadable_files"]:
                if not (self.challdir / Path(file)).exists() and not is_url(file):
                    self._raise_code("A003", "downloadable_files", file=file)

        # A004
        if not self.normalized_config["challenge_id"]:
            self._raise_code("A004", "challenge_id")

        # A005 validate regex flag contains anchors
        for flag in self.normalized_config["flags"]:
            if flag["type"] != "regex":
                continue
            if not (flag["flag"].startswith("^") and flag["flag"].endswith("$")):
                self._raise_code("A005", "flags", flag=flag["flag"])

        # A006 duplicate custom_service_types type
        type_names: set[str] = set()
        for custom_service_type in self.normalized_config["custom_service_types"]:
            type_name = custom_service_type["type"]
            if type_name in type_names:
                self._raise_code("A006", "custom_service_types", type=type_name)
            type_names.add(type_name)

        # A007 missing predefined_service display format option
        service_types = [
            {"type": "website", "display": "{url}"},
            {"type": "tcp", "display": "nc {host} {port}"},
        ] + self.normalized_config["custom_service_types"]
        for predefined_service in self.normalized_config["predefined_services"]:
            service_type = predefined_service["type"]
            type_candidate = [
                service for service in service_types if service["type"] == service_type
            ]
            # A008 missing service type
            if not type_candidate:
                self._raise_code(
                    "A008",
                    "predefined_services",
                    service_type=service_type,
                )
                continue
            string = type_candidate[0]["display"]
            for format_option in re.findall(r"(?<=\{)[^{}]+(?=\})", string):
                if not format_option in predefined_service:
                    self._raise_code(
                        "A007",
                        "predefined_services",
                        service=service_type,
                        option=format_option,
                    )

        ### CTF config validation
        # if no ctf config was provided to the validator we assume it does not exist and issue B001. not ideal as there might be other reasons for why the ctf config is not provided, but works for now
        if self.ctf_config is None:
            self._raise_code("B001")
        else:
            # B002 validate correct challenge names
            if "categories" in self.ctf_config:
                for category in self.normalized_config["categories"]:
                    if category not in self.ctf_config["categories"]:
                        self._raise_code("B002", "categories", category=category)

            # B003 validate correct author names
            if "authors" in self.ctf_config:
                for author in self.normalized_config["authors"]:
                    if author not in self.ctf_config["authors"]:
                        self._raise_code("B003", "authors", author=author)

            # B004 validate correct flag format prefix
            if (
                "flag_format_prefixes" in self.ctf_config
                and self.normalized_config["flag_format_prefix"] is not None
                and self.normalized_config["flag_format_prefix"]
                not in self.ctf_config["flag_format_prefixes"]
            ):
                self._raise_code(
                    "B004",
                    "flag_format_prefix",
                    prefix=self.normalized_config["flag_format_prefix"],
                )

        return (
            max(self.messages, key=lambda m: m["level"])["level"] < 5
            if self.messages
            else True
        ), self.messages

    def _raise_code(self, code: str, field: str | None = None, **formatting: str):
        """Adds a formatted message entry into the messages array.

        Args:
            code (*str*): The code to raise
            field (*str, None*): The exact name of the field to associate with this message if it exists, else None
            **formatting: Arguments used to format the ``formatted_message`` from codes.yml using pythons ``str.format()``. ``field_name`` is always formatted using the value from the field argument.
        """

        if code not in codes:
            raise ValueError("The specified code doesn't exist")

        # no valid field check because of A002

        self.messages.append(
            {
                "code": code,
                "field": field,
                "name": codes[code]["name"],
                "level": codes[code]["level"],
                "message": codes[code]["formatted_message"].format(
                    field_name=field, **formatting
                ),
            }
        )
