#!/usr/bin/env python3

import argparse
import subprocess
import tempfile

s3_database_bucket = "seqtoid-public-references"

workflow_versions = {
    "amr": [
        "v1.4.2"
    ],
    "benchmark": [
        "v0.0.3"
    ],
    "bulk-download": [
        "v0.0.9"
    ],
    "consensus-genome": [
        "v3.5.1",
        "v3.5.4",
        "v3.5.5"
    ],
    "diamond": [
        "v1.1.0",
        "v1.1.1"
    ],
    "host-genome-generation": [
        "v0.2.0"
    ],
    "index-generation": [
        "v2.4.8"
    ],
    # "legacy-host-filter": [ ],
    "long-read-mngs": [
        "v0.7.11"
    ],
    "minimap2": [
        "v1.0.0",
        "v1.0.1"
    ],
    "phylotree-ng": [
        "v6.11.0"
    ],
    "short-read-mngs": [
        "v8.3.11"
    ],
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


def write_aws_credentials(profile: str, file):
    aws_credentials = run_cmd(["aws", "configure", "export-credentials", "--profile", profile, "--format", "env"])
    # print("aws_credentials =", aws_credentials)
    file.write(aws_credentials)
    file.seek(0)


def main():
    parser = argparse.ArgumentParser(description="Create all Workflow Images and push them to ECR")
    parser.add_argument("-p", "--profile", type=str, help="AWS Profile", required=True)
    args = parser.parse_args()

    aws_profile = args.profile
    if not aws_profile:
        raise Exception("AWS Profile Required")
    print("aws_profile =", aws_profile)

    build_args_dict = {
        "S3_DATABASE_BUCKET": s3_database_bucket
    }
    print(f"build_args_dict =", build_args_dict)

    env_dict = {
        "DOCKER_BUILDKIT": "1"
    }
    print(f"env_dict =", env_dict)

    docker_url = docker_login(aws_profile)

    with tempfile.NamedTemporaryFile(mode='w+', delete=True) as credentials_file:
        print(f"Temporary AWS Credentials file created at: {credentials_file.name}")

        write_aws_credentials(aws_profile, credentials_file)

        for workflow_name, versions in workflow_versions.items():
            print(f"Creating Workflow [{workflow_name}]")
            # --platform linux/amd64,linux/arm64 --progress=plain #TODO:
            cmd = ["docker", "buildx", "build", "--platform", "linux/amd64", "--progress=plain", "--build-context", "lib=lib", f"workflows/{workflow_name}"]
            cmd += ["--tag", f"{docker_url}/{workflow_name}:latest"]
            cmd += ["--secret", f"id=aws,src={credentials_file.name}"]
            for k, v in build_args_dict.items():
                cmd += ["--build-arg", f"{k}={v}"]
            for version in versions:
                cmd += ["--tag", f"{docker_url}/{workflow_name}:{version}"]
            cmd += ["--push"]
            run_cmd(cmd, env=env_dict)

    print(f"Done")


if __name__ == "__main__":
    main()
