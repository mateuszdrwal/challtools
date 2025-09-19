import hashlib
import json
import urllib.parse
from pathlib import Path

import requests
from minio import Minio
from minio.error import S3Error

from challtools.constants import *
from challtools.exceptions import CriticalException
from challtools.utils import (
    build_docker_images,
    create_docker_name,
    format_user_service,
    get_docker_client,
    get_valid_config,
    load_ctf_config,
)
from challtools.validator import is_url


def run(args):
    config = get_valid_config()
    ctf_config = load_ctf_config()

    if not config["challenge_id"]:
        raise CriticalException("ID not configured in the challenge configuration file")

    if not ctf_config.get("custom", {}).get("platform_url"):
        raise CriticalException(
            "Platform URL not configured in the CTF configuration file"
        )

    if not ctf_config.get("custom", {}).get("platform_api_key"):
        raise CriticalException(
            "Platform API key not configured in the CTF configuration file"
        )

    file_urls = [file for file in config["downloadable_files"] if is_url(file)]

    if not args.skip_container_build and not args.skip_container_push:
        if build_docker_images(config, get_docker_client()):
            print(f"{BOLD}Challenge built{CLEAR}")
        else:
            print(f"{BOLD}Nothing to build{CLEAR}")

    if not args.skip_files:
        if not config["downloadable_files"]:
            print(f"{BOLD}No files defined, nothing to upload{CLEAR}")
        else:
            custom_cfg = ctf_config.get("custom", {})

            bucket_name = custom_cfg.get("s3_bucket_name") or custom_cfg.get("bucket")
            if not bucket_name:
                raise CriticalException(
                    "S3 bucket not configured in the CTF configuration file"
                )

            if not custom_cfg.get("secret"):
                raise CriticalException(
                    "Secret not configured in the CTF configuration file"
                )

            endpoint = custom_cfg.get("s3_endpoint")
            if not endpoint:
                raise CriticalException(
                    "S3 endpoint not configured in the CTF configuration file"
                )

            access_key = custom_cfg.get("s3_key")
            secret_key = custom_cfg.get("s3_secret")
            if not access_key or not secret_key:
                raise CriticalException(
                    "S3 access key/secret not configured in the CTF configuration file"
                )

            parsed_endpoint = urllib.parse.urlparse(endpoint)
            if parsed_endpoint.scheme:
                endpoint_host = parsed_endpoint.netloc or parsed_endpoint.path
                secure = parsed_endpoint.scheme == "https"
                public_endpoint = endpoint.rstrip("/")
            else:
                endpoint_host = endpoint
                secure = True
                public_endpoint = f"https://{endpoint.strip('/')}"

            try:
                s3_client = Minio(
                    endpoint_host,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=secure,
                )
            except Exception as exc:
                raise CriticalException(
                    f"Could not create MinIO client: {exc}"
                ) from exc
            folder = hashlib.sha256(
                f"{custom_cfg['secret']}-{config['challenge_id']}".encode()
            ).hexdigest()

            try:
                objects = s3_client.list_objects(
                    bucket_name, prefix=f"{folder}/", recursive=True
                )
                for obj in objects:
                    key = obj.object_name
                    print(f"{BOLD}Deleting old {key.split('/')[-1]}...{CLEAR}")
                    s3_client.remove_object(bucket_name, key)
            except S3Error as exc:
                raise CriticalException(
                    f"Could not clean up existing S3 objects: {exc}"
                ) from exc
            except Exception as exc:
                raise CriticalException(
                    f"Unexpected error cleaning S3 objects: {exc}"
                ) from exc

            filepaths = []
            for file in config["downloadable_files"]:
                if is_url(file):
                    continue

                path = Path(file)
                if path.is_dir():
                    filepaths += list(path.iterdir())
                else:
                    filepaths.append(path)

            for path in filepaths:
                if not path.exists():
                    raise CriticalException(f"file {path} does not exist!")

                key = f"{folder}/{path.name}"
                print(f"{BOLD}Uploading {path.name}...{CLEAR}")
                try:
                    s3_client.fput_object(bucket_name, key, str(path))
                except S3Error as exc:
                    raise CriticalException(
                        f"Failed to upload {path.name} to S3: {exc}"
                    ) from exc
                except Exception as exc:
                    raise CriticalException(
                        f"Unexpected error uploading {path.name} to S3: {exc}"
                    ) from exc

                file_urls.append(f"{public_endpoint}/{bucket_name}/{key}")

    if not args.skip_container_push and config["deployment"]:
        try:
            import google.auth
            import google.auth.transport.requests
        except ImportError:
            raise CriticalException("google.auth could not be imported!")

        if not ctf_config.get("custom", {}).get("container_registry"):
            raise CriticalException(
                "Docker registry has not been configured in the CTF configuration file"
            )

        print(f"{BOLD}Authenticating with registry...{CLEAR}")

        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        if not creds.valid:
            raise CriticalException("Could not authenticate with GCP")

        client = get_docker_client()
        r = client.login(
            "oauth2accesstoken",
            creds.token,
            registry=ctf_config["custom"]["container_registry"],
            reauth=True,
        )
        if not r.get("Status", "") == "Login Succeeded":
            raise CriticalException("Could not login with docker")

        for container_name, _ in config["deployment"]["containers"].items():
            container_name = create_docker_name(
                config["title"],
                container_name=container_name,
                chall_id=config["challenge_id"],
            )
            repo_container_name = urllib.parse.urljoin(
                ctf_config["custom"]["container_registry"], container_name
            )

            print(f"{BOLD}Pushing container {container_name}...{CLEAR}")
            client.images.get(container_name).tag(repo_container_name)
            stream = client.images.push(repo_container_name, stream=True)
            for log in stream:
                log = json.loads(log)
                if "error" in log:
                    raise CriticalException(
                        f"{CRITICAL}Failed pushing the container to the repository:{CLEAR}\n\033[31m{log['error']}"
                    )

    service_types = {
        s["type"]: s
        for s in [
            {"type": "website", "display": "{url}", "hyperlink": True},
            {"type": "tcp", "display": "nc {host} {port}", "hyperlink": False},
        ]
        + config["custom_service_types"]
    }

    payload = {
        "title": config["title"],
        "description": config["description"],
        "authors": config["authors"],
        "categories": config["categories"],
        "score": config["score"],
        "challenge_id": config["challenge_id"],
        "flag_format_prefix": config["flag_format_prefix"],
        "flag_format_suffix": config["flag_format_suffix"],
        "file_urls": file_urls,
        "flags": config["flags"],
        "order": config["custom"].get("order"),
        "custom": config["custom"],
        "human_metadata": config["human_metadata"],
        "services": [
            {
                "hyperlink": service_types[c["type"]]["hyperlink"],
                "user_display": format_user_service(config, c["type"], **c),
            }
            for c in config["predefined_services"]
        ],
    }

    print(f"{BOLD}Pushing to platform...{CLEAR}")

    r = requests.post(
        ctf_config["custom"]["platform_url"] + "/api/admin/push_challenge",
        json=payload,
        headers={"X-API-Key": ctf_config["custom"]["platform_api_key"]},
    )

    if r.status_code != 200:
        raise CriticalException(
            f"Request failed with status {r.status_code} - {r.json().get('message','')}"
        )

    print(f"{SUCCESS}Challenge pushed!{CLEAR}")
    return 0
