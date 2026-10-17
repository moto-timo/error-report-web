#!/bin/sh
# error-report-web - run the test suite in the production image against a
# throwaway MySQL. Used by CI; can also be run locally from the repo root.
#
# SPDX-License-Identifier: MIT

set -e

IMAGE=${IMAGE:-error-report-web-test}
NET=error-report-web-test
DB=error-report-web-test-db

docker build -t "$IMAGE" .

docker network create $NET >/dev/null
trap 'docker rm -f $DB >/dev/null; docker network rm $NET >/dev/null' EXIT

# Alias "db" matches the default DB_HOST in project/settings.py.docker;
# testingpw is not a real secret. Tests connect as root so Django can create
# the test database.
docker run -d --name $DB --network $NET --network-alias db \
    -e MYSQL_ROOT_PASSWORD=testingpw -e MYSQL_DATABASE=errorreport \
    mysql:8.0.36 >/dev/null
until docker exec $DB mysql -h127.0.0.1 -uroot -ptestingpw -e 'SELECT 1' >/dev/null 2>&1; do
    if [ "$(docker inspect -f '{{.State.Running}}' $DB)" != true ]; then
        docker logs $DB | tail -5; exit 1
    fi
    sleep 1
done

# -Wa shows deprecation warnings, i.e. what breaks on the next Django.
docker run --rm --network $NET \
    -e SECRET_KEY=ci-only \
    -e MYSQL_DATABASE=errorreport -e MYSQL_USER=root -e MYSQL_PASSWORD=testingpw \
    "$IMAGE" python3 -Wa manage.py test --noinput Post
