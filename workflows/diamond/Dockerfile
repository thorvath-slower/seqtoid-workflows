# syntax=docker/dockerfile:1.4
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
RUN sed -i s/archive.ubuntu.com/us-west-2.ec2.archive.ubuntu.com/ /etc/apt/sources.list

# ubuntu:18.04 is EOL (bumped to 22.04). Package rename on 22.04:
# libclang-common-6.0-dev (clang 6.0, 18.04) -> libclang-common-14-dev (clang 14, 22.04 default).
RUN apt-get update && apt-get -y install git gdb libclang-common-14-dev cmake g++ zlib1g-dev python3-pip

WORKDIR /tmp
RUN git clone https://github.com/morsecodist/diamond
WORKDIR /tmp/diamond
RUN git checkout minimal-mods
WORKDIR /tmp/diamond/build
RUN cmake -DCMAKE_BUILD_TYPE=Release ..
RUN make -j6
RUN mv diamond /usr/local/bin

# TODO: remove once folded into diamond branch
WORKDIR /tmp
RUN git clone https://github.com/chanzuckerberg/czid-workflows
WORKDIR /tmp/czid-workflows
RUN pip3 install -r requirements-dev.txt
COPY --from=lib idseq_utils/idseq_utils/diamond_scatter.py /usr/local/bin/

WORKDIR /workdir
