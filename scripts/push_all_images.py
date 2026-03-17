#!/usr/bin/env python3

import argparse
import boto3
import os
from pathlib import Path
import subprocess

workflow_dict = {
    "amr": {
        "versions": [
            "v1.4.2"
        ],
        "files": {
            "card.json": {
                "bucket": "seqtoid-public-references",
                "blob": "card/2023-05-22/card.json"
            }
        }
    },
    "benchmark": {
        "versions": [
            "v0.0.3"
        ]
    },
    "bulk-download": {
        "versions": [
            "v0.0.9"
        ]
    },
    "consensus-genome": {
        "versions": [
            "v3.5.1",
            "v3.5.4",
            "v3.5.5"
        ]
    },
    "diamond": {
        "versions": [
            "v1.1.0",
            "v1.1.1"
        ]
    },
    "host-genome-generation": {
        "versions": [
            "v0.2.0"
        ]
    },
    "index-generation": {
        "versions": [
            "v2.4.8"
        ]
    },
    # "legacy-host-filter": {},
    "long-read-mngs": {
        "versions": [
            "v0.7.11"
        ]
    },
    "minimap2": {
        "versions": [
            "v1.0.0",
            "v1.0.1"
        ]
    },
    "phylotree-ng": {
        "versions": [
            "v6.11.0"
        ]
    },
    "short-read-mngs": {
        "versions": [
            "v8.3.11"
        ],
        "files": {
            "HISAT2.zip": {
                "bucket": "seqtoid-public-references",
                "blob": "test/hisat2/hisat2.zip"
            }
        }
    }
}


def run_cmd(cmd, **kwargs):
    print(' '.join(cmd))
    try:
        p = subprocess.run(cmd, encoding='utf-8', stdout=subprocess.PIPE, **kwargs)
    except Exception as ex:
        print(f"Command Failed: [{cmd}]: {ex}")
        # print(traceback.format_exc())
        raise
    else:
        if p.returncode != 0:
            raise Exception(f"Command failed with code [{p.returncode}] command [{' '.join(cmd)}]")
        return p.stdout.strip()


def docker_login(profile: str):
    account = run_cmd(["aws", "sts", "get-caller-identity", "--profile", profile, "--query", "Account", "--output", "text"])
    if not account:
        raise Exception(f"AWS Profile [{profile}] has no Account")
    print(f"account = {account}")

    password = run_cmd(["aws", "ecr", "get-login-password", "--region", "us-west-2", "--profile", profile])
    # print(f"password = {password}")

    docker_url = f"{account}.dkr.ecr.us-west-2.amazonaws.com"
    print(f"docker_url = {docker_url}")

    res = run_cmd(["docker", "login", "--username", "AWS", "--password-stdin", docker_url], input=password)
    print(f"Docker Login: {res}")

    return docker_url


def download_from_s3(s3_client, bucket: str, key: str, filename: str):
    if not Path(filename).is_file():
        print(f"download_from_s3 downloading blob [{key}] => [{filename}]")
        s3_client.download_file(bucket, key, filename)
    else:
        print(f"download_from_s3: already exists [{filename}]")


def download_files_from_s3(s3_client, local_directory: str, files_config_dict: dict[str, dict]):
    print("local_directory = ", local_directory)
    # print("files_config_dict =", files_config_dict)
    if files_config_dict:
        os.makedirs(local_directory, exist_ok=True)
        for filename, blob_config_dict in files_config_dict.items():
            # print("filename =", filename)
            # print("blob_config_dict =", blob_config_dict)
            bucket = blob_config_dict["bucket"]
            # print("bucket =", bucket)
            blob = blob_config_dict["blob"]
            # print("blob =", blob)
            download_from_s3(s3_client, bucket, blob, f"{local_directory}/{filename}")
    else:
        print("No files to download from S3")


def main():
    parser = argparse.ArgumentParser(description="Create all Workflow Images and push them to ECR")
    parser.add_argument("-p", "--profile", type=str, help="AWS Profile", required=True)
    args = parser.parse_args()

    aws_profile = args.profile
    if not aws_profile:
        raise Exception("AWS Profile Required")
    print("aws_profile =", aws_profile)

    env_dict = {
        # "AWS_CREDENTIALS": aws_credentials,
        "DOCKER_BUILDKIT": "1"
    }
    # print(f"env_dict =", env_dict)

    aws_session = boto3.Session(profile_name=aws_profile)
    s3_client = aws_session.client('s3')

    docker_url = docker_login(aws_profile)

    for workflow_name, workflow_config_dict in workflow_dict.items():
        print(f"Creating Workflow [{workflow_name}]")
        # print("workflow_config =", workflow_config_dict)
        # Download S3 blobs into the workflows/<workflow_name>/tmp/ directory
        download_files_from_s3(
            s3_client,
            f"workflows/{workflow_name}/tmp",
            workflow_config_dict.get("files") or {}
        )

        # --platform linux/amd64,linux/arm64 --progress=plain #TODO:
        cmd = ["docker", "buildx", "build", "--platform", "linux/amd64", "--progress=plain", "--build-context", "lib=lib", f"workflows/{workflow_name}"]
        cmd += ["--tag", f"{docker_url}/{workflow_name}:latest"]
        versions = workflow_config_dict["versions"]
        # print("versions =", versions)
        for version in versions:
            cmd += ["--tag", f"{docker_url}/{workflow_name}:{version}"]
        cmd += ["--push"]
        run_cmd(cmd, env=env_dict)

    print(f"Done")


if __name__ == "__main__":
    main()
