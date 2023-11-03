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
