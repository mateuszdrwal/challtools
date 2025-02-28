# Setting up chroot below
FROM debian:bookworm-slim AS chroot

RUN groupadd -g 1337 ctf && useradd -r -u 1337 -g ctf ctf
RUN mkdir -p /home/ctf/

COPY service /home/ctf/

# Now setting up the actual container
FROM ghcr.io/google/nsjail/nsjail:latest

COPY --from=chroot / /chroot

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y netcat-traditional

ENTRYPOINT nsjail --port 1337 --chroot /chroot/ --user 1337 --group 1337 --cwd /home/ctf/ --tmpfsmount /tmp --bindmount_ro /etc/resolv.conf:/etc/resolv.conf /home/ctf/service

HEALTHCHECK --start-period=20s --start-interval=1s CMD nc -zv 127.0.0.1 1337 || exit 1
