#!/usr/bin/env python3

import subprocess
import warnings

workflow_versions = {
    "amr": "v1.4.2",
    "benchmark": "v0.0.3",
    "bulk-download": "v0.0.9",
    "consensus-genome": "v3.5.4",
    # "consensus-genome": "v3.5.5",
    "diamond": "v1.1.0",
    # "diamond": "v1.1.1",
    "host-genome-generation": "v0.2.0",
    "index-generation": "v2.4.8",
    "long-read-mngs": "v0.7.11",
    "minimap2": "v1.0.0",
    # "minimap2": "v1.0.1",
    "phylotree-ng": "v6.11.0",
    "short-read-mngs": "v8.3.11",
}

image_prefix = "491013321714.dkr.ecr.us-west-2.amazonaws.com"

def run_cmd(cmd):
    print(' '.join(cmd))
    try:
        res = subprocess.run(cmd)
    except Exception as ex:
        warnings.warn(ex)

def main():
    for key, value in workflow_versions.items():
        #run_cmd(["docker", "buildx", "build", "--platform", "linux/amd64", "--build-context", "lib=lib", f"workflows/{key}", "--tag", f"{image_prefix}/{key}:latest"])
        run_cmd(["docker", "tag", f"{image_prefix}/{key}:latest", f"{image_prefix}/{key}:{value}"])
        run_cmd(["docker", "push", f"{image_prefix}/{key}:latest"])
        run_cmd(["docker", "push", f"{image_prefix}/{key}:{value}"])

if __name__ == "__main__":
    main()
