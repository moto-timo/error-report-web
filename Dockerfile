# See README for how to use this.

FROM ubuntu:jammy
LABEL maintainer="Michael Halstead <mhalstead@linuxfoundation.org>"

ENV PYTHONUNBUFFERED=1 \
    LANGUAGE=en_US \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LC_CTYPE=en_US.UTF-8
## Uncomment to set proxy ENVVARS within container
#ENV http_proxy http://your.proxy.server:port
#ENV https_proxy https://your.proxy.server:port
#ENV no_proxy localhost,127.0.0.0/8

COPY requirements.txt /
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y locales \
    && echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
        && locale-gen en_US.UTF-8 \
        && update-locale \
    && apt-get install -y --no-install-recommends \
	python3-pip \
	python3-mysqldb \
	python3-dev \
	python3-wheel \
	zlib1g-dev \
	libfreetype6-dev \
	libjpeg-dev \
	default-libmysqlclient-dev \
	build-essential \
	pkg-config \
	netcat-openbsd \
	curl \
	wget \
	git \
	vim \
	zstd \
    && echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
	&& locale-gen en_US.UTF-8 \
	&& update-locale \
    && pip3 install pip --upgrade \
    && pip3 install setuptools --upgrade \
    && pip3 install gunicorn \
    && pip3 install -r /requirements.txt \
    && apt-get purge -y python3-dev build-essential pkg-config libjpeg-dev \
	&& apt-get autoremove -y \
	&& rm -rf /var/lib/apt/lists/* \
	&& apt-get clean

COPY . /opt/errorreport
COPY docker/migrate.sh /opt/migrate.sh
COPY secrets/db_user_pass.txt /run/secrets/db_user_pass
RUN echo "[client]\nname = errorsdb\nuser = errors\npassword = $(cat /run/secrets/db_user_pass)\ndefault-character-set = utf8" > /etc/mysql/conf.d/client.cnf
RUN rm -rf /opt/errorreport/docker

RUN mkdir /opt/workdir \
	&& adduser --system --uid=500 errors \
	&& chown -R errors /opt/workdir
USER errors

# Start Gunicorn
WORKDIR /opt/errorreport

CMD ["/usr/local/bin/gunicorn", "wsgi:application", "--workers=4", "--bind=:5000", "--timeout=60", "--log-level=debug", "--chdir=/opt/errorreport"]
