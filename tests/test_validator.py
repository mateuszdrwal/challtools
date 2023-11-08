from challtools.validator import ConfigValidator


def get_min_valid_config():
    return {
        "title": "testing challenge",
        "description": "testing description",
        "authors": "testing author",
        "categories": "testing category",
        "flag_format_prefix": "pytest{",
        "flags": "test_flag",
        "spec": "0.0.1",
    }


class Test_A002:
    def test_invalid(self):
        validator = ConfigValidator({})

        success, errors = validator.validate()
        assert not success
        assert any([error["code"] == "A002" for error in errors])


class Test_A005:
    def test_valid(self):
        config = get_min_valid_config()
        config["flags"] = [{"type": "regex", "flag": "^test_flag$"}]
        validator = ConfigValidator(config)

        success, errors = validator.validate()
        assert success
        assert not any([error["code"] == "A005" for error in errors])

    def test_warn(self):
        config = get_min_valid_config()
        config["flags"] = [{"type": "regex", "flag": "test_flag"}]
        validator = ConfigValidator(config)

        success, errors = validator.validate()
        assert success
        assert any([error["code"] == "A005" for error in errors])


class Test_A006:
    def test_valid(self):
        config = get_min_valid_config()
        config["custom_service_types"] = [
            {"type": "ssh", "display": "ssh display"},
            {"type": "gopher", "display": "gopher display"},
        ]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert not any([error["code"] == "A006" for error in errors])

    def test_invalid(self):
        config = get_min_valid_config()
        config["custom_service_types"] = [
            {"type": "ssh", "display": "ssh display"},
            {"type": "ssh", "display": "ssh display number two"},
        ]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert any([error["code"] == "A006" for error in errors])


class Test_A007:
    def test_valid(self):
        config = get_min_valid_config()
        config["custom_service_types"] = [
            {"type": "ssh", "display": "ssh {user}@{host} -p {port}"}
        ]
        config["predefined_services"] = [
            {"type": "ssh", "user": "root", "host": "127.0.0.1", "port": "12345"}
        ]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert not any([error["code"] == "A007" for error in errors])

    def test_invalid(self):
        config = get_min_valid_config()
        config["custom_service_types"] = [
            {"type": "ssh", "display": "ssh {user}@{host} -p {port}"}
        ]
        config["predefined_services"] = [
            {"type": "ssh", "user": "root", "host": "127.0.0.1"}
        ]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert any([error["code"] == "A007" for error in errors])


class Test_A008:
    def test_valid(self):
        config = get_min_valid_config()
        config["custom_service_types"] = [{"type": "ssh", "display": "ssh display"}]
        config["predefined_services"] = [{"type": "ssh"}]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert not any([error["code"] == "A008" for error in errors])

    def test_invalid(self):
        config = get_min_valid_config()
        config["predefined_services"] = [{"type": "gopher"}]
        validator = ConfigValidator(config)

        success, errors = validator.validate()

        assert success
        assert any([error["code"] == "A008" for error in errors])
