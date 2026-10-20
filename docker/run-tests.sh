#!/bin/sh
# Run the tests in the app image against a throwaway MariaDB. Used by CI.
#
# SPDX-License-Identifier: MIT

set -e

IMAGE=${IMAGE:-error-report-web-test}
NET=error-report-web-test
DB=error-report-web-test-db

docker build -t "$IMAGE" .

docker network create $NET >/dev/null
trap 'docker rm -f $DB >/dev/null; docker network rm $NET >/dev/null' EXIT

# Root so Django can create the test database; testingpw isn't a secret.
docker run -d --name $DB --network $NET --network-alias db \
    -e MYSQL_ROOT_PASSWORD=testingpw -e MYSQL_DATABASE=errorreport \
    mariadb:lts >/dev/null
until docker exec $DB healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; do
    if [ "$(docker inspect -f '{{.State.Running}}' $DB)" != true ]; then
        docker logs $DB | tail -5; exit 1
    fi
    sleep 1
done

# Fail on deployment warnings (hence the random key); -Wa shows deprecations.
docker run --rm --network $NET \
    -e SECRET_KEY="$(head -c 48 /dev/urandom | base64)" \
    -e MYSQL_DATABASE=errorreport -e MYSQL_USER=root -e MYSQL_PASSWORD=testingpw \
    "$IMAGE" sh -c 'python3 manage.py check --deploy --fail-level WARNING &&
        python3 -Wa manage.py test --noinput Post'
