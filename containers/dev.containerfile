from ubuntu:24.04

env DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --assume-yes \
        build-essential \
        gcc-avr \
        binutils-avr \
        avr-libc \
        avrdude \
        make \
        git && \
    rm -rf /var/lib/apt/lists/*

workdir /workspace

cmd ["bash"]
