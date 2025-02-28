FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y ssh netcat-traditional

RUN groupadd -g 1337 ctf && useradd -r -u 1337 -g ctf ctf
RUN passwd -d ctf
RUN chsh ctf -s /home/ctf/service
RUN mkdir -p /home/ctf/
RUN mkdir /run/sshd

COPY service /home/ctf/
COPY sshd_config /etc/ssh/

RUN chown -R root:ctf /home/ctf/
RUN chmod -R 750 /home/ctf/

CMD /usr/sbin/sshd -De

HEALTHCHECK --start-period=20s --start-interval=1s CMD nc -zv 127.0.0.1 22 || exit 1
