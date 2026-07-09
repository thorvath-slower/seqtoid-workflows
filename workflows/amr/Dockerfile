# syntax=docker/dockerfile:1.4
FROM ubuntu:20.04

LABEL maintainer="CZ ID Team <idseq-tech@chanzuckerberg.com>"

RUN apt-get update && apt-get -y install curl git python3 python3-pip gcc make libz-dev libncurses-dev libbz2-dev liblzma-dev g++ zip

RUN ln -s /usr/bin/python3 /usr/bin/python

# Install rgi dependencies
# CZID-78: pin versions + verify downloads with sha256 before use (fail-closed).
# TODO(CZID-78): diamond 0.8.36 ships as a prebuilt binary asset with no upstream-published
# sha256 and no authoritative source hash. Download to a file, then add a verified sha256 and a
# "sha256sum -c -" gate here (same pattern as samtools/bwa below) once obtained from a trusted copy.
RUN curl -L https://github.com/bbuchfink/diamond/releases/download/v0.8.36/diamond-linux64.tar.gz | tar xz && mv diamond /usr/local/bin
# TODO(CZID-78): oligoarrayaux is fetched over PLAIN HTTP (no TLS) from unafold.org and is
# unverified. Pin + add a verified sha256 gate (highest-priority: no transport security today).
RUN curl -L http://www.unafold.org/download/oligoarrayaux-3.8.1.tar.gz | tar xz && cd oligoarrayaux-3.8.1/ && ./configure && make install
# samtools 1.9: download, verify sha256 (authoritative), then build.
RUN curl -L -o samtools-1.9.tar.bz2 https://github.com/samtools/samtools/releases/download/1.9/samtools-1.9.tar.bz2 && \
    echo "083f688d7070082411c72c27372104ed472ed7a620591d06f928e653ebc23482  samtools-1.9.tar.bz2" | sha256sum -c - && \
    tar xjf samtools-1.9.tar.bz2 && cd samtools-1.9/ && make && mv samtools /usr/local/bin/
# bwa 0.7.17: download, verify sha256 (authoritative), then build.
RUN curl -L -o bwa-0.7.17.tar.bz2 https://github.com/lh3/bwa/releases/download/v0.7.17/bwa-0.7.17.tar.bz2 && \
    echo "de1b4d4e745c0b7fc3e107b5155a51ac063011d33a5d82696331ecf4bed8d0fd  bwa-0.7.17.tar.bz2" | sha256sum -c - && \
    tar xjf bwa-0.7.17.tar.bz2 && cd bwa-0.7.17/ && make &&  mv bwa /usr/local/bin/
# TODO(CZID-78): kma 1.4.3 is a bitbucket auto-generated tarball (checksum not guaranteed byte-stable
# upstream). Pin + add a verified sha256 gate from a trusted, archived copy.
RUN curl -L  https://bitbucket.org/genomicepidemiology/kma/get/1.4.3.tar.gz | tar xz && cd genomicepidemiology-kma-47505a7dd4eb/ && make && mv kma kma_index kma_shm kma_update /usr/local/bin/

RUN apt-get update && apt-get -y install ncbi-blast+=2.9.0-2 prodigal=1:2.6.3-4 bamtools=2.5.1+dfsg-5build1 bowtie2=2.3.5.1-6build1 bedtools=2.27.1+dfsg-4ubuntu1


COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# RGI version 6.0.3
COPY rgi_bam_parsing.patch rgi_bam_parsing.patch
# TODO(CZID-78): rgi 6.0.3 is a github auto-generated source archive (not byte-stable upstream).
# Pin + add a verified sha256 gate from a trusted, archived copy.
RUN curl -L https://github.com/arpcard/rgi/archive/refs/tags/6.0.3.tar.gz | tar xz && \
    cd rgi-6.0.3/ && \
    git apply ../rgi_bam_parsing.patch && \
    pip3 install .

# Install seqfu (used for interleaving input files)
ARG SEQFU_VER="1.16.0"
# TODO(CZID-78): SeqFu ${SEQFU_VER} is a prebuilt binary asset with no upstream-published sha256.
# Pin + add a verified sha256 gate once obtained from a trusted copy.
RUN curl -LO https://github.com/telatin/seqfu2/releases/download/v${SEQFU_VER}/SeqFu-v${SEQFU_VER}-Linux-x86_64.zip && \
    unzip SeqFu-v${SEQFU_VER}-Linux-x86_64.zip -d /usr/local/bin/

# TODO(CZID-78): seqkit v2.4.0 is a prebuilt binary asset with no upstream-published sha256.
# Pin + add a verified sha256 gate once obtained from a trusted copy.
RUN curl -LO https://github.com/shenwei356/seqkit/releases/download/v2.4.0/seqkit_linux_amd64.tar.gz && tar zxvf seqkit_linux_amd64.tar.gz \
    && mv seqkit /usr/local/bin/ && rm seqkit_linux_amd64.tar.gz

# load databases
# TODO(CZID-78): card.json (2023-05-22) is an unverified reference DATABASE download (data, not
# executed). Add a verified sha256 gate once obtained from a trusted copy.
RUN curl -LO https://czid-public-references.s3.us-west-2.amazonaws.com/card/2023-05-22/card.json && \
    rgi card_annotation -i card.json && \
    rgi load \
        --card_annotation card_database_v3.2.6.fasta \
        -i card.json 

COPY --from=lib /bin/log_assembly_fail.py /usr/local/bin/log_assembly_fail.py
COPY empty-main-header.txt /tmp/empty-main-header.txt 
