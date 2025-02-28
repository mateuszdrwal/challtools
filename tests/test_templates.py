import os
import time
import pytest
import requests
from pwn import remote
from challtools.utils import get_valid_config, start_chall
from utils import main_wrapper


def run_template_test(tmp_path, docker_client, template_name):
    os.chdir(tmp_path)
    assert main_wrapper(["init", template_name]) == 0
    assert main_wrapper(["build"]) == 0

    config = get_valid_config()
    containers, service_strings = start_chall(config)
    assert len(containers) == 1
    container = containers[0]
    print(f"Service strings: {service_strings}")

    try:
        start_time = time.time()
        while (
            "Health" not in container.attrs["State"]
            or container.attrs["State"]["Health"]["Status"] != "healthy"
        ):
            if time.time() - start_time > 20:
                raise TimeoutError("Container healthcheck timed out")
            time.sleep(0.5)
            container.reload()

        if service_strings[0].startswith("http://"):
            response = requests.get(service_strings[0])
            assert "CTF{template_flag}" in response.text
            assert response.status_code == 200

        elif service_strings[0].startswith("nc "):
            host, port = service_strings[0].split(" ")[1:]
            with remote(host, int(port)) as r:
                data = r.recvline().decode()
                assert "CTF{template_flag}" in data

        elif service_strings[0].startswith("ncat --ssl "):
            host, port = service_strings[0].split(" ")[2:]
            with remote(host, int(port), ssl=True) as r:
                data = r.recvline().decode()
                assert "CTF{template_flag}" in data

        # FIXME: pwntools ssh doesn't work that great, the below hangs at connection
        # elif service_strings[0].startswith("ssh "):
        #     user, host = service_strings[0].split(" ")[1].split("@")
        #     port = service_strings[0].split(" ")[3]
        #     with ssh(host=host, port=int(port), user=user, password="") as connection:
        #         data = connection.readline().decode()
        #         assert "CTF{template_flag}" in data
        else:
            raise ValueError("Unsupported service string")

    finally:
        container.kill()
        container.remove()


@pytest.mark.fails_without_docker
def test_flask_template(tmp_path, docker_client):
    run_template_test(tmp_path, docker_client, "flask")


@pytest.mark.fails_without_docker
def test_php_template(tmp_path, docker_client):
    run_template_test(tmp_path, docker_client, "php")


# pwntools ssh doesn't work that great, so this is not trivial to test
# @pytest.mark.fails_without_docker
# def test_ssh_template(tmp_path, docker_client):
#     run_template_test(tmp_path, docker_client, "ssh")


@pytest.mark.fails_without_docker
def test_tcp_nsjail_template(tmp_path, docker_client):
    run_template_test(tmp_path, docker_client, "tcp_nsjail")


@pytest.mark.fails_without_docker
def test_tls_nsjail_template(tmp_path, docker_client):
    run_template_test(tmp_path, docker_client, "tls_nsjail")
