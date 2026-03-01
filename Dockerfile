FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# OBS PPA provides libobs-dev matching current stable OBS releases
RUN apt-get update \
    && apt-get install -y software-properties-common \
    && add-apt-repository ppa:obsproject/obs-studio \
    && apt-get update \
    && apt-get install -y \
        cmake \
        gcc \
        g++ \
        libobs-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

RUN cmake -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/output \
    && cmake --build build \
    && cmake --install build
