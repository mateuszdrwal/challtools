import os
from pathlib import Path
import yaml
import pytest
from challtools.utils import build_chall, get_valid_config
from utils import populate_dir, main_wrapper, inittemplatepath


class Test_allchalls:
    def test_validate(self, tmp_path, capsys):
        populate_dir(tmp_path, "simple_ctf")
        assert main_wrapper(["allchalls", "validate"]) == 0
        assert capsys.readouterr().out.count("Validation succeeded.") == 3

    def test_no_ctf_config(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        Path("ctf.yml").unlink()
        assert main_wrapper(["allchalls", "validate"]) == 1


class Test_validate:
    def test_ok(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert main_wrapper(["validate"]) == 0

    def test_ok_subdir(self, tmp_path):
        populate_dir(tmp_path, "subdir")
        os.chdir("subdir")
        assert main_wrapper(["validate"]) == 0

    def test_schema_violation(self, tmp_path, capsys):
        populate_dir(tmp_path, "schema_violation")
        assert main_wrapper(["validate"]) == 1
        assert "A002" in capsys.readouterr().out

    def test_schema_violation_list(self, tmp_path, capsys):
        populate_dir(tmp_path, "schema_violation_list")
        assert main_wrapper(["validate"]) == 1
        assert "A002" in capsys.readouterr().out


class Test_build:
    # TODO build scripts
    def test_no_service(self, tmp_path, capsys):
        populate_dir(tmp_path, "minimal_valid")
        assert main_wrapper(["build"]) == 0
        assert "nothing to do" in capsys.readouterr().out.lower()

    @pytest.mark.fails_without_docker
    def test_single(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        assert main_wrapper(["build"]) == 0
        assert "challtools_test_challenge_f9629917705648c9:latest" in [
            tag for image in docker_client.images.list() for tag in image.tags
        ]

    @pytest.mark.fails_without_docker
    def test_subdir(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        os.chdir("container")
        assert main_wrapper(["build"]) == 0
        assert "challtools_test_challenge_f9629917705648c9:latest" in [
            tag for image in docker_client.images.list() for tag in image.tags
        ]

    @pytest.mark.fails_without_docker
    def test_solution(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp_solution")
        assert main_wrapper(["build"]) == 0
        import time

        time.sleep(3)
        tags = [tag for image in docker_client.images.list() for tag in image.tags]
        assert "challtools_test_challenge_f9629917705648c9:latest" in tags
        assert "sol_challtools_test_9461485faadf529f:latest" in tags

    @pytest.mark.fails_without_docker
    def test_build_error(self, tmp_path, capsys, clean_container_state):
        populate_dir(tmp_path, "build_error")
        assert main_wrapper(["build"]) == 1
        assert "copy failed:" in capsys.readouterr().out.lower()

    @pytest.mark.fails_without_docker
    def test_parse_error(self, tmp_path, capsys, clean_container_state):
        populate_dir(tmp_path, "dockerfile_parse_error")
        assert main_wrapper(["build"]) == 1
        assert "dockerfile parse error" in capsys.readouterr().out.lower()


# TODO tricky as it blocks
# class Test_start:
#     pass


class Test_solve:
    def test_no_service(self, tmp_path, capsys):
        populate_dir(tmp_path, "minimal_valid")
        build_chall(get_valid_config())
        assert main_wrapper(["solve"]) == 0
        assert "no solution defined" in capsys.readouterr().out.lower()

    @pytest.mark.fails_without_docker
    def test_ok(self, tmp_path, capsys, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp_solution")
        build_chall(get_valid_config())
        assert main_wrapper(["solve"]) == 0
        assert "solved" in capsys.readouterr().out.lower()

    @pytest.mark.fails_without_docker
    def test_fail(self, tmp_path, capsys, clean_container_state):
        populate_dir(tmp_path, "broken_solution")
        build_chall(get_valid_config())
        assert main_wrapper(["solve"]) == 1
        assert "could not be solved" in capsys.readouterr().out.lower()


class Test_compose:
    # TODO challenges with muliple containers
    def test_no_service(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert main_wrapper(["compose"]) == 0
        assert not Path("docker-compose.yml").exists()

    def test_single(self, tmp_path):
        populate_dir(tmp_path, "trivial_tcp")
        assert main_wrapper(["compose"]) == 0
        assert Path("docker-compose.yml").exists()
        compose = yaml.safe_load(Path("docker-compose.yml").read_text())
        assert len(compose) == 2
        assert compose.get("services") == {
            "challenge": {"build": "container", "ports": ["50000:13337"]}
        }


class Test_ensureid:
    def test_ok(self, tmp_path, capsys):
        populate_dir(tmp_path, "minimal_valid")
        assert main_wrapper(["ensureid"]) == 0
        assert get_valid_config()["challenge_id"]
        assert "written" in capsys.readouterr().out.lower()

    def test_has_id(self, tmp_path, capsys):
        populate_dir(tmp_path, "has_id")
        assert main_wrapper(["ensureid"]) == 0
        assert get_valid_config()["challenge_id"]
        assert "present" in capsys.readouterr().out.lower()


class Test_init:
    def check_identical(self, tmp_path, template):
        if not (
            len(list(tmp_path.rglob("*")))
            == len(list((inittemplatepath / template).rglob("*"))) - 1
        ):  # account for DESCRIPTION
            return False

        for path in tmp_path.rglob("*"):

            if not (inittemplatepath / template / path.relative_to(tmp_path)).exists():
                return False

            if not path.read_bytes() == (
                inittemplatepath / template / path.relative_to(tmp_path)
            ).read_bytes() and path.name not in ["challenge.yml", "challenge.yaml"]:
                return False

        return True

    def test_empty(self, tmp_path, capsys):
        os.chdir(tmp_path)
        assert main_wrapper(["init"]) == 0
        assert "initialized" in capsys.readouterr().out.lower()
        assert self.check_identical(tmp_path, "default")

    def test_nonempty(self, tmp_path):
        os.chdir(tmp_path)
        Path("existing_file").touch()
        assert main_wrapper(["init", "default"]) == 1
        assert not self.check_identical(tmp_path, "default")

    def test_force(self, tmp_path):
        os.chdir(tmp_path)
        Path("existing_file").touch()
        assert main_wrapper(["init", "default", "-f"]) == 0
        assert not self.check_identical(tmp_path, "default")
        Path("existing_file").unlink()
        assert self.check_identical(tmp_path, "default")

    def test_list(self, capsys):
        assert main_wrapper(["init", "--list"]) == 0
        assert (
            "default - a generic template suitable for any type of challenge"
            in capsys.readouterr().out.lower()
        )
