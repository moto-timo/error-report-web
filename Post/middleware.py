# SPDX-License-Identifier: MIT
#
# error-reporting-tool - middleware
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Add a Content-Security-Policy header to every response.

    The policy is read from settings.CONTENT_SECURITY_POLICY, a dict mapping
    each directive to a list of sources (an empty list gives a directive with
    no value, e.g. 'upgrade-insecure-requests'). When
    settings.CONTENT_SECURITY_POLICY_REPORT_ONLY is True the policy is sent
    as Content-Security-Policy-Report-Only instead, so violations are
    reported by browsers but not blocked.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        policy = getattr(settings, 'CONTENT_SECURITY_POLICY', None) or {}
        self.policy = "; ".join(
            " ".join([directive] + list(sources))
            for directive, sources in policy.items())

        if getattr(settings, 'CONTENT_SECURITY_POLICY_REPORT_ONLY', False):
            self.header = 'Content-Security-Policy-Report-Only'
        else:
            self.header = 'Content-Security-Policy'

    def __call__(self, request):
        response = self.get_response(request)

        # Leave alone any policy a view has set itself
        if self.policy and self.header not in response:
            response[self.header] = self.policy

        return response
