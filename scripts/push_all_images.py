#!/usr/bin/env python3

import subprocess
import warnings

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


def run_cmd(cmd, input=None):
    print(' '.join(cmd))
    try:
        if input is None:
            p = subprocess.run(cmd, encoding='utf-8', stdout=subprocess.PIPE)
        else:
            p = subprocess.run(cmd, input=input, encoding='utf-8', stdout=subprocess.PIPE)
        if p.returncode != 0:
            raise Exception("Command failed!")
        return p.stdout.strip()
    except Exception as ex:
        warnings.warn(ex)
        raise


account = run_cmd(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
docker_url = f"{account}.dkr.ecr.us-west-2.amazonaws.com"
print(f"docker_url = {docker_url}")

password = run_cmd(["aws", "ecr", "get-login-password", "--region", "us-west-2"])
# print(f"password = {password}")

res = run_cmd(["docker", "login", "--username", "AWS", "--password-stdin", docker_url], password)
print(f"Docker Login: {res}")


def main():
    for module, versions in workflow_versions.items():
        # --platform linux/amd64,linux/arm64
        cmd = ["docker", "buildx", "build", "--platform", "linux/amd64", "--build-context", "lib=lib", f"workflows/{module}"]
        cmd += ["--tag", f"{docker_url}/{module}:latest"]
        for version in versions:
            cmd += ["--tag", f"{docker_url}/{module}:{version}"]
        cmd += ["--push"]
        run_cmd(cmd)


if __name__ == "__main__":
    main()
