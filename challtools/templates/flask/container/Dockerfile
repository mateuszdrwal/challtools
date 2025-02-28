FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y python3 python3-pip python3-flask gunicorn nginx curl

RUN groupadd -g 1337 ctf && useradd -r -u 1337 -g ctf ctf
RUN mkdir -p /home/ctf/

COPY server.py /home/ctf/
COPY nginx.conf /etc/nginx/nginx.conf

RUN chown -R root:ctf /home/ctf/
RUN chmod -R 750 /home/ctf/

WORKDIR /home/ctf/

CMD nginx && gunicorn server:app -b unix:/tmp/ctf.sock -u ctf -g ctf

HEALTHCHECK --start-period=20s --start-interval=1s CMD curl -f http://127.0.0.1:1337/ || exit 1
