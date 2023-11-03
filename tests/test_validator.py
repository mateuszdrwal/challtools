from challtools.validator import ConfigValidator

class Test_A002:
    def test_invalid(self):
        validator = ConfigValidator({})

        success, errors = validator.validate()
        assert not success
        assert any(error["code"] == "A002" for error in errors)
