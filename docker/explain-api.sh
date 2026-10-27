#!/bin/sh
# Show how the database plans the JSON API's queries, and check that they
# use the expected indexes. EXPLAIN only plans a query, so this is safe to
# run against a live database; --analyze also runs them and adds the rows
# they really read (r_rows).
#
# Run from the checkout on the server, e.g.:
#
#   docker/explain-api.sh -f docker-compose.prod.yaml [--analyze] [recipe [machine]]
#
# The recipe and machine default to those of the latest failure.
#
# SPDX-License-Identifier: MIT

set -e

COMPOSE_FILE=docker-compose.yaml
EXPLAIN=EXPLAIN
while [ $# -gt 0 ]; do
    case "$1" in
    -f) COMPOSE_FILE=$2; shift 2 ;;
    --analyze) EXPLAIN=ANALYZE; shift ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Unknown option $1" >&2; exit 2 ;;
    *) break ;;
    esac
done

# Run SQL from stdin in the db container, with tab-separated output. The
# password goes in the environment so that it doesn't show up in ps.
sql() {
    docker compose -f "$COMPOSE_FILE" exec -T db sh -c \
        'MYSQL_PWD="$MYSQL_PASSWORD" exec mariadb -u"$MYSQL_USER" "$MYSQL_DATABASE" -B "$@"' sh "$@"
}

quote() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"
}

latest() {
    echo "SELECT $1 FROM Post_buildfailure f JOIN Post_build b ON f.BUILD_id = b.id
          ORDER BY b.DATE DESC LIMIT 1;" | sql -N
}
RECIPE=${1:-$(latest f.RECIPE)}
MACHINE=${2:-$(latest b.MACHINE)}
FAIL_ID=$(latest f.id)

echo "Failures: $(echo 'SELECT COUNT(*) FROM Post_buildfailure;' | sql -N)," \
     "builds: $(echo 'SELECT COUNT(*) FROM Post_build;' | sql -N)"
echo "Using recipe $RECIPE, machine $MACHINE, failure $FAIL_ID"

FAILED=0

# check NAME KEY SQL: plan SQL, print the plan, and check that it uses the
# index KEY without reading through a whole table (KEY - skips the index
# check)
check() {
    name=$1 key=$2 query=$3
    echo
    echo "== $name"
    plan=$(echo "$EXPLAIN $query" | sql)
    if command -v column >/dev/null; then
        echo "$plan" | column -t -s "$(printf '\t')"
    else
        echo "$plan"
    fi

    problems=
    if [ "$key" != - ] && ! echo "$plan" | awk -F '\t' -v key="$key" \
            'NR > 1 && $6 == key { found = 1 } END { exit !found }'; then
        problems="does not use $key"
    fi
    # Reading or sorting the rows an index finds is fine; reading a whole
    # table or index (type ALL or index) is not, once it is large
    scans=$(echo "$plan" | awk -F '\t' \
        'NR > 1 && ($4 == "ALL" || $4 == "index") && $9 > 10000 { printf "%s%s (%s rows)", sep, $3, $9; sep = ", " }')
    if [ -n "$scans" ]; then
        problems="${problems:+$problems, }reads all of $scans"
    fi

    if [ -n "$problems" ]; then
        echo "-- WARNING: $problems"
        FAILED=$((FAILED + 1))
    else
        echo "-- OK"
    fi
}

JOIN="FROM Post_buildfailure f JOIN Post_build b ON f.BUILD_id = b.id"

check "failures/ (newest first)" idx_date \
    "SELECT f.id $JOIN ORDER BY b.DATE DESC, b.id DESC LIMIT 25"
check "failures/?recipe=" idx_recipe \
    "SELECT f.id $JOIN WHERE f.RECIPE = $(quote "$RECIPE") ORDER BY b.DATE DESC, b.id DESC LIMIT 25"
check "failures/?recipe= (count)" idx_recipe \
    "SELECT COUNT(*) FROM Post_buildfailure f WHERE f.RECIPE = $(quote "$RECIPE")"
check "failures/?machine=" - \
    "SELECT f.id $JOIN WHERE b.MACHINE = $(quote "$MACHINE") ORDER BY b.DATE DESC, b.id DESC LIMIT 25"
check "failures/?since= (last 7 days)" idx_date \
    "SELECT f.id $JOIN WHERE b.DATE >= NOW() - INTERVAL 7 DAY ORDER BY b.DATE DESC, b.id DESC LIMIT 25"
check "failures/$FAIL_ID/similar/" idx_task_lev \
    "SELECT s.id FROM Post_buildfailure f
     JOIN Post_buildfailure s ON s.TASK = f.TASK
          AND s.LEV_DISTANCE BETWEEN f.LEV_DISTANCE AND f.LEV_DISTANCE + 10
     WHERE f.id = $FAIL_ID AND s.id <> f.id LIMIT 25"

echo
if [ "$FAILED" -gt 0 ]; then
    echo "$FAILED of the plans above need a look."
    exit 1
fi
echo "All plans use the expected indexes."
