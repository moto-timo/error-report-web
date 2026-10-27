import datetime
import urllib.request
import urllib.parse
import urllib.error
import json
from unittest.mock import patch
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db import OperationalError, connection
import re
from django.test import Client, TestCase, override_settings
from Post.models import BuildFailure, Build
from Post.validators import clean_link_back
from Post.views import ER_STATEMENT_TIMEOUT, search_time_limit

#Delete the data between tests
def data_runner (func):
    def wrap(*args, **kwargs):

        self = args[0]

        bo = Build.objects.all()
        bfo = BuildFailure.objects.all()

        bo.delete()
        bfo.delete()

        # run the test
        func(*args, **kwargs)

        # The submission should have added one row in each table
        self.assertEqual(bfo.count(), 1)
        self.assertEqual(bo.count(), 1)

        compare_db_obj_with_payload(self, bfo[0])

        self.assertIsNotNone(bfo[0].LEV_DISTANCE)

        self.after_submission_test_links()

    return wrap

def compare_db_obj_with_payload(self, bf_object):
    f = open("test-data/test-payload.json")
    data = f.read()
    payload = json.loads(data)

    self.assertEqual(bf_object.BUILD.MACHINE == str(payload['machine']), True)
    self.assertEqual(bf_object.BUILD.NATIVELSBSTRING == str(payload['nativelsb']), True)
    self.assertEqual(bf_object.BUILD.TARGET_SYS == str(payload['target_sys']), True)

    self.assertEqual(bf_object.BUILD.BUILD_SYS == str(payload['build_sys']), True)
    self.assertEqual(bf_object.BUILD.DISTRO == str(payload['distro']), True)
    self.assertEqual(bf_object.BUILD.NAME == str(payload['username']), True)
    self.assertEqual(bf_object.BUILD.EMAIL == str(payload['email']), True)
    self.assertEqual(bf_object.BUILD.LINK_BACK == payload.get("link_back", None), True)

    g = re.match(r'(.*): (.*)', payload['branch_commit'])

    self.assertEqual(bf_object.BUILD.BRANCH == str(g.group(1)), True)
    self.assertEqual(bf_object.BUILD.COMMIT == str(g.group(2)), True)

    fail = payload['failures'][0]
    package = str(fail['package'])
    g = re.match(r'(.*)\-(\d.*)', package)

    self.assertEqual(bf_object.ERROR_DETAILS == str(fail['log']), True)
    self.assertEqual(bf_object.TASK == str(fail['task']), True)
    self.assertEqual(bf_object.RECIPE == str(g.group(1)), True)
    self.assertEqual(bf_object.RECIPE_VERSION == str(g.group(2)), True)

    f.close()

class SimpleTest(TestCase):
    def setUp(self):
        # The test clients submit with HTTP_HOST="testhost", so allow it here
        # instead of hardcoding a test host into the project settings.
        override = override_settings(ALLOWED_HOSTS=["testhost"])
        override.enable()
        self.addCleanup(override.disable)
        self.client = Client(HTTP_HOST="testhost")
        self.client_0_3 = Client(HTTP_HOST="testhost", HTTP_USER_AGENT="send-error-report/0.3")

    def after_submission_test_links(self):
        response = self.client.get('/Errors/Latest/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/Statistics/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/Errors/Build/1/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/Errors/Details/1/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/Errors/SimilarTo/1/')
        self.assertEqual(response.status_code, 200)

    # Opening test-payload.json and submitting it to server
    # expecting json response 1st item inserted to db
    @data_runner
    def test_submission(self):

        with open("test-data/test-payload.json") as f:
            data = f.read()


        data = urllib.parse.urlencode({'data': data})

        response = self.client.post("/ClientPost/",
                                    data,
                                    "application/json")

        self.assertEqual(response.status_code, 200)
        # Now let's see if the data entered the db
        data_ob = BuildFailure.objects.get()

        self.assertEqual("/Build/"+str(data_ob.BUILD.id) in response.content.decode('utf-8'), True)

        self.assertEqual("tester" in data_ob.BUILD.NAME, True)

    @data_runner
    def test_submission_0_3(self):
        with open("test-data/test-payload.json") as f:
            data = f.read()

        response = self.client_0_3.post("/ClientPost/",
                                        data,
                                        "application/json")

        self.assertEqual(response.status_code, 200)

        # Now let's see if the data entered the db
        data_ob = BuildFailure.objects.get()

        self.assertEqual("/Build/"+str(data_ob.BUILD.id) in response.content.decode('utf-8'), True)

        self.assertEqual("tester" in data_ob.BUILD.NAME, True)

    @data_runner
    def test_submission_ret_json(self):

        with open("test-data/test-payload.json") as f:
            data = f.read()

        data = urllib.parse.urlencode({'data': data})

        response = self.client.post("/ClientPost/JSON/",
                                    data,
                                    "application/json")

        self.assertEqual(response.status_code, 200)

        ret = json.loads(response.content)

        # Now let's see if the data entered the db
        data_ob = BuildFailure.objects.get()

        self.assertEqual(ret['build_id'], data_ob.BUILD.id)
        fails = ret['failures']

        self.assertEqual(fails[0]['id'], data_ob.id)
        self.assertEqual("tester" in data_ob.BUILD.NAME, True)


    @data_runner
    def test_submission_ret_json_0_3(self):

        with open("test-data/test-payload.json") as f:
            data = f.read()

        response = self.client_0_3.post("/ClientPost/JSON/",
                                        data,
                                        "application/json")

        self.assertEqual(response.status_code, 200)

        ret = json.loads(response.content)

        data_ob = BuildFailure.objects.get()
        self.assertEqual(ret['build_id'], data_ob.BUILD.id)
        fails = ret['failures']

        self.assertEqual(fails[0]['id'], data_ob.id)

        # Now let's see if the data entered the db
        self.assertEqual("tester" in data_ob.BUILD.NAME, True)



    # Submitting invalid json to server expecting Invalid json in response
    def test_invalid_json(self):
        response = self.client.post("/ClientPost/",
                                    "data=woeifjopeijefowiejfoweijfo",
                                    "application/json")


        self.assertEqual("Invalid json" in response.content.decode('utf-8'), True)


    # Submitting invalid json to server expecting Invalid json in
    # a json response
    def test_invalid_json_ret_json(self):
        response = self.client.post("/ClientPost/JSON/",
                                    "data=woeifjopeijefowiejfoweijfo",
                                    "application/json")


        ret = json.loads(response.content)

        self.assertEqual(response.status_code, 500)
        self.assertEqual("Invalid json" in ret['error'], True)


     # Submitting valid json to server with fields missing
    def test_missing_fields_ret_json(self):

        response = self.client.post("/ClientPost/JSON/",
                                    "data={}",
                                    "application/json")


        ret = json.loads(response.content)

        self.assertEqual(response.status_code, 500)
        self.assertEqual("Problem reading json payload" in ret['error'],
                         True)

    # Test invalid parameters
    def test_invalid_parms(self):

        response = self.client.get("/Errors/Latest/?order_by=BUILD")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?filter=wefwfe")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?filter=wefwfe&type=wefijwoe")
        response = self.client.get("/Errors/Latest/?page=-1")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?page=wefwef")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?limit=-1")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?limit=wefwef")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/Errors/Latest/?order_by=-BUILD&filter=wefwef&type=dewwef&limit=wefe&page=wefwef")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/Errors/Build/9898989898/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/Errors/SimilarTo/9898989898/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/Errors/Details/9898989898/")
        self.assertEqual(response.status_code, 200)

@override_settings(ALLOWED_HOSTS=["testhost"])
class CSPTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="testhost")

    def test_csp_header(self):
        for url in ('/Statistics/', '/Errors/Latest/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            csp = response['Content-Security-Policy']
            self.assertIn("script-src 'self'", csp)
            self.assertIn("style-src 'self'", csp)
            self.assertIn("object-src 'none'", csp)
            self.assertNotIn("unsafe-inline", csp)
            self.assertNotIn("unsafe-eval", csp)

    def test_security_headers(self):
        response = self.client.get('/Statistics/')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_hsts_only_over_https_from_proxy(self):
        self.assertNotIn('Strict-Transport-Security', self.client.get('/Statistics/'))
        response = self.client.get('/Statistics/', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=31536000')

    def test_csp_report_only(self):
        with override_settings(CONTENT_SECURITY_POLICY_REPORT_ONLY=True):
            # New client so the middleware picks up the setting
            response = Client(HTTP_HOST="testhost").get('/Statistics/')
        self.assertIn('Content-Security-Policy-Report-Only', response)
        self.assertNotIn('Content-Security-Policy', response)

    def test_csp_disabled(self):
        with override_settings(CONTENT_SECURITY_POLICY=None):
            response = Client(HTTP_HOST="testhost").get('/Statistics/')
        self.assertNotIn('Content-Security-Policy', response)

    def test_no_inline_script_or_style(self):
        Build.objects.all().delete()

        with open("test-data/test-payload.json") as f:
            data = urllib.parse.urlencode({'data': f.read()})
        response = self.client.post("/ClientPost/", data, "application/json")
        self.assertEqual(response.status_code, 200)

        build = Build.objects.get()
        failure = BuildFailure.objects.get()
        urls = ['/Statistics/',
                '/Errors/Statistics/MACHINE/',
                '/Errors/Latest/',
                '/Errors/Build/%d/' % build.id,
                '/Errors/Details/%d/' % failure.id]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            content = response.content.decode('utf-8')
            self.assertIsNone(re.search(r'\sstyle\s*=', content), url)
            # Only external scripts and non-executed JSON data are allowed
            for script in re.findall(r'<script[^>]*>', content):
                self.assertTrue(re.search(r'\ssrc\s*=', script) or
                                'type="application/json"' in script,
                                "%s: %s" % (url, script))

        response = self.client.get('/Errors/Statistics/MACHINE/')
        self.assertIn(build.MACHINE, response.content.decode('utf-8'))

        Build.objects.all().delete()

class LinkBackValidatorTest(TestCase):

    def test_allows_http(self):
        self.assertEqual(clean_link_back("http://example.com/build/1"),
                         "http://example.com/build/1")

    def test_allows_https(self):
        self.assertEqual(clean_link_back("https://example.com/build/1"),
                         "https://example.com/build/1")

    def test_rejects_javascript(self):
        self.assertIsNone(
            clean_link_back("javascript:alert(document.domain)//PROBE"))

    def test_rejects_data(self):
        self.assertIsNone(
            clean_link_back("data:text/html,<script>alert(1)</script>"))

    def test_rejects_vbscript(self):
        self.assertIsNone(clean_link_back("vbscript:msgbox(1)"))

    def test_rejects_scheme_relative(self):
        self.assertIsNone(clean_link_back("//evil.example.com/x"))

    def test_rejects_schemeless(self):
        self.assertIsNone(clean_link_back("example.com/build/1"))

    def test_rejects_control_char_obfuscation(self):
        self.assertIsNone(clean_link_back("java\tscript:alert(1)"))

    def test_rejects_leading_whitespace(self):
        self.assertIsNone(clean_link_back("  javascript:alert(1)"))

    def test_rejects_missing_host(self):
        self.assertIsNone(clean_link_back("http:///path"))

    def test_rejects_none_empty_and_non_string(self):
        self.assertIsNone(clean_link_back(None))
        self.assertIsNone(clean_link_back(""))
        self.assertIsNone(clean_link_back("   "))
        self.assertIsNone(clean_link_back(123))


class LinkBackSubmissionTest(TestCase):

    def setUp(self):
        # The test client submits with HTTP_HOST="testhost"; allow it here.
        override = override_settings(ALLOWED_HOSTS=["testhost"])
        override.enable()
        self.addCleanup(override.disable)
        self.client = Client(HTTP_HOST="testhost")
        with open("test-data/test-payload.json") as f:
            self.base_payload = json.loads(f.read())

    def tearDown(self):
        Build.objects.all().delete()
        BuildFailure.objects.all().delete()

    def _submit(self, link_back):
        payload = dict(self.base_payload)
        payload['link_back'] = link_back
        data = urllib.parse.urlencode({'data': json.dumps(payload)})
        response = self.client.post("/ClientPost/", data, "application/json")
        self.assertEqual(response.status_code, 200, response.content)
        return BuildFailure.objects.get()

    def test_javascript_link_back_is_blanked(self):
        bf = self._submit("javascript:alert(document.domain)//PROBE")
        self.assertIsNone(bf.BUILD.LINK_BACK)

        response = self.client.get("/Errors/Details/%d/" % bf.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'href="javascript:', response.content)

    def test_http_link_back_is_preserved(self):
        bf = self._submit("http://example.com/build/42")
        self.assertEqual(bf.BUILD.LINK_BACK, "http://example.com/build/42")



@override_settings(ALLOWED_HOSTS=["testhost"])
class PaginationTest(TestCase):
    def test_invalid_page_shows_last_page(self):
        client = Client(HTTP_HOST="testhost")
        for page in ("999", "abc"):
            response = client.get("/Errors/Latest/", {"page": page})
            self.assertEqual(response.status_code, 200)


@override_settings(ALLOWED_HOSTS=["testhost"])
class SpecialSubmitterTest(TestCase):
    def test_tab_shown_only_when_configured(self):
        client = Client(HTTP_HOST="testhost")
        self.assertNotContains(client.get("/Errors/Latest/"), "Latest Autobuilder errors")
        with self.settings(SPECIAL_SUBMITTER={"name": "yocto-autobuilder",
                                              "title": "Autobuilder",
                                              "link": "Autobuilder"}):
            self.assertContains(client.get("/Errors/Latest/"), "Latest Autobuilder errors")


@override_settings(ALLOWED_HOSTS=["testhost"])
class AccountPagesRemovedTest(TestCase):
    def test_accounts_urls_are_gone(self):
        client = Client(HTTP_HOST="testhost")
        for url in ("/accounts/register/", "/accounts/login/"):
            self.assertEqual(client.get(url).status_code, 404)
        # The admin keeps its own login page.
        self.assertEqual(client.get("/admin/login/").status_code, 200)


@override_settings(ALLOWED_HOSTS=["testhost"])
class SubmittedHtmlTest(TestCase):
    """Submitted data must only ever reach the page escaped."""

    def submit(self, **fields):
        with open("test-data/test-payload.json") as f:
            payload = json.load(f)
        payload.update(fields)
        payload['failures'][0]['package'] = '<b>evil</b>-1.0'
        payload['failures'][0]['task'] = 'do_<b>evil</b>'
        client = Client(HTTP_HOST="testhost")
        data = urllib.parse.urlencode({'data': json.dumps(payload)})
        self.assertEqual(client.post("/ClientPost/", data, "application/json").status_code, 200)
        return client, BuildFailure.objects.get()

    def test_failure_fields_are_escaped(self):
        client, bf = self.submit()
        response = client.get("/Errors/Latest/")
        self.assertNotContains(response, "<b>evil</b>")
        self.assertContains(response, "Filter by &lt;b&gt;evil&lt;/b&gt;: do_&lt;b&gt;evil&lt;/b&gt;")

    def test_commit_is_not_in_html_attributes(self):
        client, bf = self.submit(branch_commit="master: <b>evil</b>")
        response = client.get("/Errors/Latest/")
        self.assertNotContains(response, "<b>evil</b>")
        self.assertContains(response, 'data-commit="&lt;b&gt;evil&lt;/b&gt;"')
        # With html enabled, Bootstrap inserts these as HTML.
        self.assertNotContains(response, "data-content")
        self.assertNotContains(response, "data-html")

    def test_build_fields_are_stored_as_sent_and_escaped(self):
        client, bf = self.submit(machine="<script>alert(1)</script>")
        # Stored as sent; escaped on output.
        self.assertEqual(bf.BUILD.MACHINE, "<script>alert(1)</script>")
        for url in ("/Errors/Latest/", "/Errors/Details/%d/" % bf.id,
                    "/Errors/Statistics/MACHINE"):
            response = client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, "<script>alert", msg_prefix=url)

    def test_tooltips_are_not_html(self):
        with open("Post/static/js/main.js") as f:
            self.assertNotRegex(f.read(), r"tooltip\(\{[^}]*html: true")


@patch("Post.management.commands.culldb.time.sleep")
class CullDbTest(TestCase):
    def setUp(self):
        for _ in range(3):
            Build.objects.create()

    def test_culls_to_size(self, _sleep):
        call_command("culldb", "1")
        self.assertEqual(Build.objects.count(), 1)

    def test_zero_culls_everything(self, _sleep):
        call_command("culldb", "0")
        self.assertEqual(Build.objects.count(), 0)

    def test_info_deletes_nothing(self, _sleep):
        call_command("culldb", "--info")
        self.assertEqual(Build.objects.count(), 3)


@override_settings(ALLOWED_HOSTS=["testhost"])
class ApiTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="testhost")
        self.builds = []
        for i, machine in enumerate(("qemux86-64", "qemuarm64")):
            build = Build.objects.create(
                DATE=datetime.datetime(2026, 10, i + 1, tzinfo=datetime.timezone.utc),
                MACHINE=machine, BRANCH="master", COMMIT="abc%d" % i,
                TARGET="core-image-minimal", DISTRO="poky",
                NATIVELSBSTRING="ubuntu-24.04", BUILD_SYS="x86_64-linux",
                TARGET_SYS="x86_64-poky-linux", NAME="tester",
                EMAIL="tester@example.com")
            BuildFailure.objects.create(
                TASK="do_compile", RECIPE="busybox", RECIPE_VERSION="1.36",
                ERROR_DETAILS="error: oops %d" % i, BUILD=build)
            self.builds.append(build)

    def test_list(self):
        response = self.client.get("/api/v1/failures/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        # Newest first by default
        self.assertEqual(data["results"][0]["build"]["machine"], "qemuarm64")
        self.assertNotIn("error_details", data["results"][0])

    def test_email_not_exposed(self):
        failure = BuildFailure.objects.first()
        for url in ("/api/v1/failures/",
                    "/api/v1/failures/%d/" % failure.id,
                    "/api/v1/builds/%d/" % failure.BUILD.id):
            self.assertNotContains(self.client.get(url), "tester@example.com")

    def test_filters(self):
        def count(**params):
            return self.client.get("/api/v1/failures/", params).json()["count"]
        self.assertEqual(count(machine="qemuarm64"), 1)
        self.assertEqual(count(recipe="busybox", task="do_compile"), 2)
        self.assertEqual(count(since="2026-10-02"), 1)
        self.assertEqual(count(until="2026-10-01"), 1)
        self.assertEqual(count(machine="nope"), 0)

    def test_pagination(self):
        data = self.client.get("/api/v1/failures/", {"limit": 1}).json()
        self.assertEqual(data["num_pages"], 2)
        self.assertIsNone(data["previous"])
        second = self.client.get(data["next"]).json()
        self.assertEqual(second["page"], 2)
        self.assertNotEqual(second["results"][0]["id"], data["results"][0]["id"])

    def test_pagination_with_same_date(self):
        # Builds often share a DATE; paging must still show each failure once
        date = self.builds[0].DATE
        for i in range(5):
            build = Build.objects.create(
                DATE=date, MACHINE="qemux86", BRANCH="master", COMMIT="c%d" % i,
                TARGET="", DISTRO="poky", NATIVELSBSTRING="", BUILD_SYS="",
                TARGET_SYS="", NAME="tester", EMAIL="")
            for task in ("do_compile", "do_install"):
                BuildFailure.objects.create(
                    TASK=task, RECIPE="busybox", RECIPE_VERSION="1.36",
                    ERROR_DETAILS="error", BUILD=build)
        for order_by in ("-date", "date"):
            ids = []
            url = "/api/v1/failures/?limit=3&order_by=" + order_by
            while url:
                data = self.client.get(url).json()
                ids += [result["id"] for result in data["results"]]
                url = data["next"]
            self.assertEqual(sorted(ids),
                             sorted(BuildFailure.objects.values_list("id", flat=True)))

    def test_bad_parameters(self):
        for params in ({"limit": "0"}, {"limit": "1000"}, {"limit": "x"},
                       {"page": "x"}, {"page": "99"}, {"order_by": "EMAIL"},
                       {"order_by": "recipe"}, {"order_by": "id"},
                       {"since": "yesterday"}):
            response = self.client.get("/api/v1/failures/", params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn("error", response.json())

    def test_detail(self):
        failure = BuildFailure.objects.order_by("id").first()
        data = self.client.get("/api/v1/failures/%d/" % failure.id).json()
        self.assertEqual(data["error_details"], "error: oops 0")
        self.assertIn("similar_count", data)
        self.assertEqual(self.client.get(data["similar_url"]).status_code, 200)

    def test_detail_does_not_change_referer(self):
        failure = BuildFailure.objects.first()
        self.client.get("/api/v1/failures/%d/" % failure.id)
        failure.refresh_from_db()
        self.assertEqual(failure.REFERER, "NOT_VISITED")

    def test_build(self):
        build = self.builds[0]
        data = self.client.get("/api/v1/builds/%d/" % build.id).json()
        self.assertEqual(data["machine"], "qemux86-64")
        self.assertEqual(len(data["failures"]), 1)

    def test_not_found(self):
        for url in ("/api/v1/failures/999999/", "/api/v1/failures/999999/similar/",
                    "/api/v1/builds/999999/"):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_get_only(self):
        # As on the site, where the CSRF check refuses a POST before the
        # view's require_GET can
        client = Client(HTTP_HOST="testhost", enforce_csrf_checks=True)
        self.assertEqual(client.post("/api/v1/failures/").status_code, 403)


@override_settings(ALLOWED_HOSTS=["testhost"])
class SearchTimeLimitTest(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="testhost")

    def search(self, error):
        # Fail the search's page(), then let the empty page that replaces it
        # through
        empty = Paginator(BuildFailure.objects.none(), 25).page(1)
        with patch("Post.views.Paginator.page", side_effect=[error, empty]):
            return self.client.get("/Errors/Search/", {"query": "oops"})

    def test_timeout_shows_message(self):
        response = self.search(OperationalError(
            ER_STATEMENT_TIMEOUT,
            "Query was interrupted: execution time limit 10 sec exceeded"))
        self.assertContains(response, "took too long", status_code=503)
        self.assertContains(response, "stopped after 10 seconds", status_code=503)

    def test_other_errors_are_raised(self):
        with self.assertRaises(OperationalError):
            self.search(OperationalError(2006, "MySQL server has gone away"))

    def test_limit_stops_query(self):
        if connection.vendor != "mysql" or not connection.mysql_is_mariadb:
            self.skipTest("needs MariaDB")
        with self.settings(SEARCH_TIME_LIMIT=0.1), connection.cursor() as cursor:
            with self.assertRaises(OperationalError) as cm:
                with search_time_limit():
                    cursor.execute("SELECT COUNT(*) FROM seq_1_to_1000000000"
                                   " WHERE MD5(seq) = 'x'")
            self.assertEqual(cm.exception.args[0], ER_STATEMENT_TIMEOUT)
            cursor.execute("SELECT @@max_statement_time")
            self.assertEqual(cursor.fetchone()[0], 0)
