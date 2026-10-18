# Set real values in a local commit on the server; never push them.
# Commented-out secrets stop the service starting.
#SECRET_KEY=<set this here>
DEBUG=0
ALLOWED_HOSTS=errors.yoctoproject.org
MYSQL_DATABASE=errorreport
MYSQL_USER=errorreport
#MYSQL_PASSWORD=<set this here, same as in .env.prod.db>
#CSP_REPORT_ONLY=1
