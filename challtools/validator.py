import os
from copy import deepcopy
import json
from pathlib import Path
import pkg_resources
import yaml
from jsonschema import validate, ValidationError, Draft7Validator, validators

with pkg_resources.resource_stream("challtools", "codes.yml") as f:
    codes = yaml.safe_load(f)

with pkg_resources.resource_stream("challtools", "challenge.schema.json") as f:
    schema = json.load(f)


def is_url(s):
    return s.startswith("http://") or s.startswith("https://")


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema2):
        if instance is not None:
            for property2, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(property2, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema2,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingDraft7Validator = extend_with_default(Draft7Validator)


class ConfigValidator:
    def __init__(self, config, ctf_config=None, challdir=None):
        if not isinstance(config, dict):
            raise ValueError("Config parameter needs to be a dict")
        self.messages = []
        self.config = {}
        self.normalized_config = {}
        self.config = config
        self.ctf_config = ctf_config
        self.challdir = challdir

    # def normalize_challenge(self):
    #     """Returns a version of the challenge config where all defaults have been substituted in and fields expecting an array are formatted with an array, even if only one element without the array was provided.

    #     Returns:
    #         dict: A normalized version of the challenge config
    #     """

    #     return DefaultValidatingDraft7Validator(schema).validate(self.normalized_config)

    def validate(self):
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

        from pprint import pprint

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
                True,
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
            self.normalized_config["deployment"] = {
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
                        "privileged": self.normalized_config["service"]["privileged"],
                    },
                },
                "networks": {},
                "volumes": {},
            }
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

        ### CTF config validation
        # if no ctf config was provided to the validator we assume it does not exist and issue B001. not ideal as there might be other reasons for why the ctf config is not provided, but works for now
        if self.ctf_config == None:
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
                and self.normalized_config["flag_format_prefix"]
                not in self.ctf_config["flag_format_prefixes"]
            ):
                self._raise_code(
                    "B004",
                    "flag_format_prefix",
                    prefix=self.normalized_config["flag_format_prefix"],
                )

        return True, self.messages

    def _raise_code(self, code, field=None, **formatting):
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
