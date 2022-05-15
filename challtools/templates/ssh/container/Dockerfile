FROM ubuntu:20.04

RUN apt-get update
RUN apt-get install -y ssh

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
