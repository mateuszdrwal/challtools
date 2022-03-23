import os
import re
from pathlib import Path
import pytest
import yaml
from challtools.utils import (
    CriticalException,
    process_messages,
    get_ctf_config_path,
    load_ctf_config,
    load_config,
    get_valid_config,
    discover_challenges,
    get_first_text_flag,
    create_docker_name,
    format_user_service,
    validate_solution_output,
    validate_flag,
    build_image,
    build_chall,
    start_chall,
    start_solution,
)
from utils import populate_dir


# TODO
# class Test_process_messages:
#     pass


class Test_get_ctf_config_path:
    def test_root(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        assert get_ctf_config_path() == tmp_path / "ctf.yml"

    def test_subdir(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        os.chdir("chall1")
        assert get_ctf_config_path() == tmp_path / "ctf.yml"

    def test_yaml(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        Path("ctf.yml").rename("ctf.yaml")
        assert get_ctf_config_path() == tmp_path / "ctf.yaml"

    def test_missing(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert get_ctf_config_path() is None


class Test_load_ctf_config:
    def test_empty(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        assert load_ctf_config() == {}

    def test_populated(self, tmp_path):
        populate_dir(tmp_path, "ctf_authors")
        assert load_ctf_config() == yaml.safe_load((tmp_path / "ctf.yml").read_text())

    def test_missing(self, tmp_path):
        os.chdir(tmp_path)
        assert load_ctf_config() == None


class Test_load_config:
    def test_root(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert load_config() == yaml.safe_load((tmp_path / "challenge.yml").read_text())

    def test_subdir(self, tmp_path):
        populate_dir(tmp_path, "subdir")
        os.chdir("subdir")
        assert load_config() == yaml.safe_load((tmp_path / "challenge.yml").read_text())

    def test_yaml(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        Path("challenge.yml").rename("challenge.yaml")
        assert load_config() == yaml.safe_load(
            (tmp_path / "challenge.yaml").read_text()
        )

    def test_missing(self, tmp_path):
        os.chdir(tmp_path)
        with pytest.raises(CriticalException):
            load_config()


class Test_get_valid_config:
    def test_valid(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert get_valid_config()

    def test_invalid(self, tmp_path):
        populate_dir(tmp_path, "schema_violation")
        with pytest.raises(CriticalException):
            get_valid_config()

    def test_invalid_list(self, tmp_path):
        populate_dir(tmp_path, "schema_violation_list")
        with pytest.raises(CriticalException):
            get_valid_config()


class Test_discover_challenges:
    def test_root(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        assert set(discover_challenges()) == {
            tmp_path / "chall1" / "challenge.yml",
            tmp_path / "chall2" / "challenge.yml",
            tmp_path / "chall3" / "challenge.yml",
        }

    def test_subdir(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        os.chdir(tmp_path / "chall1")
        assert set(discover_challenges()) == {
            tmp_path / "chall1" / "challenge.yml",
            tmp_path / "chall2" / "challenge.yml",
            tmp_path / "chall3" / "challenge.yml",
        }

    def test_yaml(self, tmp_path):
        populate_dir(tmp_path, "simple_ctf")
        (tmp_path / "chall2" / "challenge.yml").rename(
            tmp_path / "chall2" / "challenge.yaml"
        )
        assert set(discover_challenges()) == {
            tmp_path / "chall1" / "challenge.yml",
            tmp_path / "chall2" / "challenge.yaml",
            tmp_path / "chall3" / "challenge.yml",
        }


class Test_get_first_text_flag:
    def test_exists(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        assert get_first_text_flag(get_valid_config()) == "CTF{d3f4ul7_fl46}"

    def test_missing(self, tmp_path):
        populate_dir(tmp_path, "regex_flag")
        assert get_first_text_flag(get_valid_config()) is None


class Test_create_docker_name:
    def check_valid(self, name):
        assert all(ord(c) < 128 for c in name)
        # docker tags can typically be 128 long, but here we check for 124 since challtools prefixes solution cointainers with "sol_"
        assert re.match(r"[\w][\w.-]{,123}", name)

    def test_basic(self):
        self.check_valid(create_docker_name("challenge"))

    def test_long_title(self):
        self.check_valid(create_docker_name("challenge" * 128))

    def test_container(self):
        self.check_valid(create_docker_name("challenge", container_name="container"))

    def test_container_long(self):
        self.check_valid(
            create_docker_name("challenge", container_name="container" * 128)
        )

    def test_chall_id(self):
        self.check_valid(create_docker_name("challenge", chall_id="ididididid"))

    def test_chall_id_long(self):
        self.check_valid(create_docker_name("challenge", chall_id="ididididid" * 128))

    def test_all_long(self):
        self.check_valid(
            create_docker_name(
                "challenge" * 128,
                container_name="container" * 128,
                chall_id="ididididid" * 128,
            )
        )


class Test_format_user_service:
    def test_tcp(self):
        assert (
            format_user_service(
                {"custom_service_types": []}, "tcp", host="127.0.0.1", port="1337"
            )
            == "nc 127.0.0.1 1337"
        )

    def test_website(self):
        assert (
            format_user_service(
                {"custom_service_types": []}, "website", url="http://127.0.0.1:1337"
            )
            == "http://127.0.0.1:1337"
        )

    def test_custom(self):
        assert (
            format_user_service(
                {
                    "custom_service_types": [
                        {
                            "type": "htjp",
                            "display": "htjp://{host}:{port}",
                        }
                    ]
                },
                "htjp",
                host="127.0.0.1",
                port="1337",
            )
            == "htjp://127.0.0.1:1337"
        )


class Test_validate_flag:
    def test_default(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        config = get_valid_config()
        assert validate_flag(config, "CTF{d3f4ul7_fl46}")
        assert not validate_flag(config, "CTF{invalid}")
        assert not validate_flag(config, "d3f4ul7_fl46")

    def test_no_format(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        config = get_valid_config()
        config["flag_format_prefix"] = None
        assert validate_flag(config, "d3f4ul7_fl46")
        assert not validate_flag(config, "CTF{d3f4ul7_fl46}")

    def test_multiple(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        config = get_valid_config()
        config["flags"].append({"type": "text", "flag": "second_valid"})
        assert validate_flag(config, "CTF{d3f4ul7_fl46}")
        assert validate_flag(config, "CTF{second_valid}")

    def test_regex(self, tmp_path):
        populate_dir(tmp_path, "minimal_valid")
        config = get_valid_config()
        config["flags"] = [{"type": "regex", "flag": r"^\d{8}$"}]
        assert validate_flag(config, "CTF{12345678}")
        assert validate_flag(config, "CTF{87654321}")
        assert not validate_flag(config, "CTF{12345678K}")
        assert not validate_flag(config, "12345678")


class Test_build_image:
    @pytest.mark.fails_without_docker
    def test_simple(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        build_image("container", "challtools_test", docker_client)
        assert "challtools_test:latest" in [
            tag for image in docker_client.images.list() for tag in image.tags
        ]


class Test_build_chall:
    # TODO challenges with muliple containers
    # TODO build scripts
    @pytest.mark.fails_without_docker
    def test_trivial_tcp(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        assert build_chall(get_valid_config())
        assert "challtools_test_challenge_f9629917705648c9:latest" in [
            tag for image in docker_client.images.list() for tag in image.tags
        ]

    @pytest.mark.fails_without_docker
    def test_solution(self, tmp_path, docker_client, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp_solution")
        assert build_chall(get_valid_config())
        tags = [tag for image in docker_client.images.list() for tag in image.tags]
        assert "challtools_test_challenge_f9629917705648c9:latest" in tags
        assert "sol_challtools_test_9461485faadf529f:latest" in tags


class Test_start_chall:
    # TODO challenges with muliple containers
    @pytest.mark.fails_without_docker
    def test_single(self, tmp_path, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        config = get_valid_config()
        build_chall(config)
        containers, services = start_chall(config)
        assert len(containers) == len(services) == 1
        assert re.match(r"nc 127.0.0.1 \d+", services[0])

    @pytest.mark.fails_without_docker
    def test_missing(self, tmp_path, clean_container_state):
        populate_dir(tmp_path, "minimal_valid")
        config = get_valid_config()
        build_chall(config)
        containers, services = start_chall(config)
        assert len(containers) == len(services) == 0


class Test_start_solution:
    @pytest.mark.fails_without_docker
    def test_simple(self, tmp_path, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp_solution")
        config = get_valid_config()
        build_chall(config)
        container = start_solution(config)
        assert container.image.tags[0] == "sol_challtools_test_9461485faadf529f:latest"

    @pytest.mark.fails_without_docker
    def test_missing(self, tmp_path, clean_container_state):
        populate_dir(tmp_path, "trivial_tcp")
        config = get_valid_config()
        build_chall(config)
        container = start_solution(config)
        assert container is None
