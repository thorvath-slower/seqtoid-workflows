#!/usr/bin/env python3

import argparse
import os
import subprocess
import tempfile

#
# This script takes the version(s) of each workflow, which is usually a git release tag, like "vxX.Y.Z" for "WORKFLOW_NAME-vX.Y.Z"
# 1. Builds a Docker image for the Dockerfile for WORKFLOW_NAME at the given tag(s)
# 2. Pushes Docker image to EMR
# 3. Uploads all WDL files for WORKFLOW_NAME at the given tag to the czid-workflows S3 bucket
#
# TODO: Build based on Git TAG instead of the main branch; this used to be done in the workflows-infra task, and maybe should be done so again
# TODO: Even better, have GitHub Actions for each Workflow, with optional Version. But still might be ideal if ran from the workflow infra project
#

database_bucket = "seqtoid-public-references"
workflows_dir = "workflows"
# wdl_profile = "idseq-sandbox"

workflow_to_versions_dict = {
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
        "v0.7.11",
        "v0.7.12",
    ],
    "minimap2": [
        "v1.0.0",
        "v1.0.1"
    ],
    "phylotree-ng": [ # TODO: This doesn't match any versions in CZI, and is unused. So why build it at all?
        "v6.11.0"
    ],
    "short-read-mngs": [
        "v8.3.11",
        "v8.3.15"
    ],
}

build_args_dict = {
    "S3_DATABASE_BUCKET": database_bucket
}

env_dict = {
    "DOCKER_BUILDKIT": "1"
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


def get_aws_account_id(profile: str):
    account_id = run_cmd(["aws", "sts", "get-caller-identity", "--profile", profile, "--query", "Account", "--output", "text"])
    if not account_id:
        raise Exception(f"AWS Profile [{profile}] has no Account")
    print(f"account_id = ", account_id)
    return account_id


def docker_login(profile: str):
    account_id = get_aws_account_id(profile)

    password = run_cmd(["aws", "ecr", "get-login-password", "--region", "us-west-2", "--profile", profile])
    # print(f"password = {password}")

    docker_url = f"{account_id}.dkr.ecr.us-west-2.amazonaws.com"
    print(f"docker_url = ", docker_url)

    login_response = run_cmd(["docker", "login", "--username", "AWS", "--password-stdin", docker_url], input=password)
    print(f"Docker Login: ", login_response)

    return docker_url


def write_aws_credentials(profile: str, credentials_file):
    aws_credentials = run_cmd(["aws", "configure", "export-credentials", "--profile", profile, "--format", "env"])
    # print("aws_credentials =", aws_credentials)
    credentials_file.write(aws_credentials)
    credentials_file.seek(0)


def push_workflow_to_ecr(workflow_name: str, workflow_versions: list[str], docker_url: str, credentials_filename: str):
    print(f"Creating Workflow Image [{workflow_name}] versions {workflow_versions}")
    # --platform linux/amd64,linux/arm64 --progress=plain #TODO:
    cmd = [
        "docker", "buildx", "build",
        "--platform", "linux/amd64",
        "--progress=plain",
        "--build-context", "lib=lib",
        f"{workflows_dir}/{workflow_name}"
    ]
    cmd += ["--tag", f"{docker_url}/{workflow_name}:latest"]
    cmd += ["--secret", f"id=aws,src={credentials_filename}"]
    for build_arg_key, build_arg_value in build_args_dict.items():
        cmd += ["--build-arg", f"{build_arg_key}={build_arg_value}"]
    for workflow_version in workflow_versions:
        cmd += ["--tag", f"{docker_url}/{workflow_name}:{workflow_version}"]
    cmd += ["--push"]
    push_result = run_cmd(cmd, env=env_dict)
    print("push_result = ", push_result)


def push_all_workflows_to_ecr(profile: str):
    print(f"build_args_dict =", build_args_dict)
    print(f"env_dict =", env_dict)

    docker_url = docker_login(profile)

    with tempfile.NamedTemporaryFile(mode='w+', delete=True) as credentials_file:
        print(f"Temporary AWS Credentials file created at: {credentials_file.name}")

        write_aws_credentials(profile, credentials_file)

        for workflow_name, workflow_versions in workflow_to_versions_dict.items():
            push_workflow_to_ecr(
                workflow_name=workflow_name,
                workflow_versions=workflow_versions,
                docker_url=docker_url,
                credentials_filename=credentials_file.name,
            )


def list_local_files(local_dir: str):
    for (root_dir, sub_dirs, filenames) in os.walk(local_dir):
        for filename in filenames:
            if filename.endswith(".wdl") or filename.endswith(".json") or filename.endswith(".wdl.zip"):
                yield filename
        break  # Only return files in local_dir, not subdirectories


def list_remote_files(profile: str,bucket:str, prefix:str):
    query_process = subprocess.run(
        ["aws", "s3api", "list-objects", "--bucket", bucket, "--prefix", prefix, "--output", "json", "--profile", profile],
        check=True,
        capture_output=True
    )
    jq_process = subprocess.run(
        ['jq', '-r', '.Contents[]?.Key'],
        input=query_process.stdout,
        capture_output=True
    )
    for line in jq_process.stdout.decode('utf-8').strip().splitlines():
        # print("line =", line)
        yield line.removeprefix(prefix)


def push_workflow_to_s3(profile: str, workflow_name: str, workflow_version: str, workflows_bucket: str):
    print(f"Copying Workflow to S3 [{workflow_name}] version [{workflow_version}]")

    #
    # List all files in S3 and locally, and make sure there aren't incongruous files in S3.
    # TODO: Currently we only verify all relevant local files already exist in S3, not whether S3 contains extra files
    #

    prefix = f"{workflow_name}-{workflow_version}"
    s3_dir_uri = f"s3://{workflows_bucket}/{prefix}"
    print(f"s3_dir_uri =", s3_dir_uri)
    remote_filenames = set(list_remote_files(
        profile=profile,
        bucket=workflows_bucket,
        prefix=f"{prefix}/"
    ))

    # if not remote_filenames:
    #     raise Exception(f"S3 Workflow contains no files: {s3_dir_uri}/")
    print(f"remote_filenames =", sorted(remote_filenames))

    local_dir = f"workflows/{workflow_name}"
    local_filenames = sorted(list_local_files(f"{local_dir}/"))

    if not local_filenames:
        raise Exception(f"Workflow dir contains no relevant files: {local_dir}/")
    print('local_filenames =', local_filenames)

    # for filename in local_filenames:
    #     if filename not in remote_filenames:
    #         raise Exception(f"Local file [{filename}] does not exist in S3: {s3_dir_uri}/")

    #
    # Copy relevant files to S3
    #

    for filename in local_filenames:
        local_filepath = f"{local_dir}/{filename}"
        print(f"Uploading file [{local_filepath}] to S3 [{s3_dir_uri}/]")

        # git show "${WORKFLOW_TAG}:${file}" | aws s3 cp --acl public-read - "$s3_url"
        # copy_status = run_cmd(["aws", "s3", "cp", "--acl", "public-read", f"{local_dir}/{local_file}", f"{s3_dir_uri}/"])
        s3_cp_result = run_cmd(["aws", "s3", "cp", f"{local_filepath}", f"{s3_dir_uri}/{filename}", "--profile", profile])
        print("s3_cp_result = ", s3_cp_result)
        # If zipped WDL doesn't exist, create and then copy it; Or maybe delete it, and ALWAYS re-create it?
        #  create f"{local_filepath}.zip" and then copy that zip file into S3
        if local_filepath.endswith('.wdl'):
            local_filepath_zipped = f"{local_filepath}.zip"
            if not os.path.isfile(local_filepath_zipped):
                zip_result = run_cmd(["miniwdl", "zip", local_filepath, "--output", local_filepath_zipped, "--path", local_dir])
                print("zip_result = ", zip_result)
                s3_cp_zip_result = run_cmd(["aws", "s3", "cp", f"{local_filepath}.zip", f"{s3_dir_uri}/{filename}.zip", "--profile", profile])
                print("s3_cp_zip_result = ", s3_cp_zip_result)


# TODO: Only do this for Prod / idseq-prod => [ $(aws iam list-account-aliases | jq -r '.AccountAliases[0]') == "idseq-prod"]]; then
def push_all_workflows_to_s3(profile: str, environment: str):
    # if profile != wdl_profile:
    #     raise Exception(f"Run this script in the {wdl_profile} AWS account to publish WDL files to S3")

    account_id = get_aws_account_id(profile)
    workflows_bucket = f"seqtoid-workflows-{environment}-{account_id}"
    # workflows_bucket = "cypherid-samples-deleteme"

    for workflow_name, workflow_versions in workflow_to_versions_dict.items():
        for workflow_version in workflow_versions:
            push_workflow_to_s3(
                profile=profile,
                workflow_name=workflow_name,
                workflow_version=workflow_version,
                workflows_bucket=workflows_bucket
            )


def main():
    parser = argparse.ArgumentParser(description="Create all Workflow Images and push them to ECR")
    parser.add_argument("-p", "--profile", type=str, help="AWS Profile", required=True)
    parser.add_argument("-e", "--environment", type=str, choices=['sandbox', 'dev', 'staging', 'prod'], help="AWS Environment", required=True)
    parser.add_argument("-d", "--destination", type=str, choices=['all', 's3', 'ecr'], help="AWS Destination", required=True)
    args = parser.parse_args()

    print("profile =", args.profile)
    print("environment =", args.environment)
    print("destination =", args.destination)

    if args.destination == 's3':
        push_all_workflows_to_s3(args.profile, args.environment)
    elif args.destination == 'ecr':
        push_all_workflows_to_ecr(args.profile)
    else:
        push_all_workflows_to_s3(args.profile, args.environment)
        push_all_workflows_to_ecr(args.profile)

    print(f"Done")


if __name__ == "__main__":
    main()
