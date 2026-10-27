# SPDX-License-Identifier: MIT
#
# error-reporting-tool - read-only JSON API
#
# Licensed under the MIT license, see COPYING.MIT for details

import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import connection
from django.db.models import F
from django.db.models.expressions import RawSQL
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET

from Post.models import Build, BuildFailure

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# Query parameter -> exact match field
FILTERS = {
    'recipe': 'RECIPE',
    'recipe_version': 'RECIPE_VERSION',
    'task': 'TASK',
    'build': 'BUILD',
    'error_type': 'BUILD__ERROR_TYPE',
    'machine': 'BUILD__MACHINE',
    'distro': 'BUILD__DISTRO',
    'target': 'BUILD__TARGET',
    'branch': 'BUILD__BRANCH',
    'commit': 'BUILD__COMMIT',
    'build_sys': 'BUILD__BUILD_SYS',
    'target_sys': 'BUILD__TARGET_SYS',
    'nativelsbstring': 'BUILD__NATIVELSBSTRING',
    'submitter': 'BUILD__NAME',
}

# Post_build.id. F('BUILD__id') would give Post_buildfailure.BUILD_id
# instead, which isn't in idx_date. The SQL is only quoted constant names,
# so there is nothing to inject.
BUILD_ID = RawSQL('%s.%s' % (connection.ops.quote_name(Build._meta.db_table),  # noqa: S611
                             connection.ops.quote_name('id')), ())


class BadRequest(Exception):
    pass


def error(message, status):
    return JsonResponse({'error': message}, status=status)


def build_dict(request, build):
    # The submitter's email is left out so that it can't be harvested in bulk
    return {
        'id': build.id,
        'url': request.build_absolute_uri(
            reverse('build_errors', args=[build.id])),
        'api_url': request.build_absolute_uri(
            reverse('api_build', args=[build.id])),
        'date': build.DATE.isoformat() if build.DATE else None,
        'error_type': build.ERROR_TYPE,
        'machine': build.MACHINE,
        'distro': build.DISTRO,
        'target': build.TARGET,
        'branch': build.BRANCH,
        'commit': build.COMMIT,
        'build_sys': build.BUILD_SYS,
        'target_sys': build.TARGET_SYS,
        'nativelsbstring': build.NATIVELSBSTRING,
        'submitter': build.NAME,
        'link_back': build.LINK_BACK,
    }


def failure_dict(request, failure, build=True):
    ret = {
        'id': failure.id,
        'url': request.build_absolute_uri(
            reverse('details', args=[failure.id])),
        'api_url': request.build_absolute_uri(
            reverse('api_failure', args=[failure.id])),
        'task': failure.TASK,
        'recipe': failure.RECIPE,
        'recipe_version': failure.RECIPE_VERSION,
    }
    if build:
        ret['build'] = build_dict(request, failure.BUILD)
    return ret


def parse_when(value, name, end_of_day=False):
    when = parse_datetime(value)
    if when is None:
        day = parse_date(value)
        if day is None:
            raise BadRequest("Invalid %s: %s" % (name, value))
        when = datetime.datetime.combine(
            day, datetime.time.max if end_of_day else datetime.time.min)
    if timezone.is_naive(when):
        when = timezone.make_aware(when, datetime.timezone.utc)
    return when


def paginate(request, items, to_dict):
    try:
        limit = int(request.GET.get('limit', DEFAULT_LIMIT))
    except ValueError:
        raise BadRequest("Invalid limit")
    if not 0 < limit <= MAX_LIMIT:
        raise BadRequest("limit must be between 1 and %d" % MAX_LIMIT)

    # Sort only the ids and then fetch the page's rows: to sort whole rows
    # the database reads every one that matches, and the logs make the rows
    # large even when they aren't selected
    paginator = Paginator(items.values_list('id', flat=True), limit)
    try:
        page = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        raise BadRequest("Invalid page")
    except EmptyPage:
        raise BadRequest("No such page")

    def page_url(number):
        query = request.GET.copy()
        query['page'] = number
        return request.build_absolute_uri('?' + query.urlencode())

    ids = list(page)
    rows = items.in_bulk(ids)

    return {
        'count': paginator.count,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'next': page_url(page.next_page_number()) if page.has_next() else None,
        'previous': page_url(page.previous_page_number())
                    if page.has_previous() else None,
        'results': [to_dict(rows[id]) for id in ids],
    }


def filter_failures(request, items):
    for param, field in FILTERS.items():
        if param in request.GET:
            items = items.filter(**{field: request.GET[param]})

    if 'since' in request.GET:
        items = items.filter(
            BUILD__DATE__gte=parse_when(request.GET['since'], 'since'))
    if 'until' in request.GET:
        items = items.filter(
            BUILD__DATE__lte=parse_when(request.GET['until'], 'until',
                                        end_of_day=True))

    # Only dates: sorting on other fields reads every failure, and ids are
    # in date order anyway
    order_by = request.GET.get('order_by', '-date')
    if order_by not in ('date', '-date'):
        raise BadRequest("Invalid order_by: %s" % order_by)
    # Break ties so that pages don't overlap; builds often share a DATE,
    # which older databases store to the second. Break them on the build
    # id, which idx_date holds, so that the database can walk the index
    # rather than sort every row. Failures in one build come back in the
    # order of the BUILD_id index.
    ordering = [F('BUILD__DATE'), BUILD_ID]
    if order_by.startswith('-'):
        ordering = [o.desc() for o in ordering]
    else:
        ordering = [o.asc() for o in ordering]

    # Lists don't show the logs, so don't load them
    return items.order_by(*ordering).defer('ERROR_DETAILS')


@require_GET
def failures(request):
    try:
        items = filter_failures(request,
                                BuildFailure.objects.select_related('BUILD'))
        data = paginate(request, items,
                        lambda failure: failure_dict(request, failure))
    except BadRequest as e:
        return error(str(e), 400)
    return JsonResponse(data)


@require_GET
def failure(request, fail_id):
    try:
        failure = BuildFailure.objects.select_related('BUILD').get(id=fail_id)
    except ObjectDoesNotExist:
        return error("Not found", 404)

    data = failure_dict(request, failure)
    data['error_details'] = failure.ERROR_DETAILS
    data['similar_count'] = failure.get_similar_fails_count()
    data['similar_url'] = request.build_absolute_uri(
        reverse('api_similar', args=[failure.id]))
    return JsonResponse(data)


@require_GET
def similar(request, fail_id):
    try:
        failure = BuildFailure.objects.get(id=fail_id)
    except ObjectDoesNotExist:
        return error("Not found", 404)

    try:
        items = filter_failures(
            request, failure.get_similar_fails().select_related('BUILD'))
        data = paginate(request, items,
                        lambda failure: failure_dict(request, failure))
    except BadRequest as e:
        return error(str(e), 400)
    return JsonResponse(data)


@require_GET
def build(request, build_id):
    try:
        build = Build.objects.get(id=build_id)
    except ObjectDoesNotExist:
        return error("Not found", 404)

    data = build_dict(request, build)
    data['failures'] = [failure_dict(request, failure, build=False)
                        for failure in build.buildfailure_set.order_by('id')]
    return JsonResponse(data)
