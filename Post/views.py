# error-reporting-tool - view definitions
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

# Create your views here.
from __future__ import division
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.core.context_processors import csrf
from django.shortcuts import HttpResponse
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render_to_response
from django.template import RequestContext, loader
from Post.models import Build, BuildFailure
from django.contrib.auth import authenticate
from django.core.mail import send_mail, BadHeaderError
import os, sys, random
from parser import Parser
from getInfo import Info
from createStatistics import Statistics
from django.utils import simplejson
import json
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import redirect
from django.core.urlresolvers import reverse_lazy
from django.contrib.sites.models import RequestSite
from collections import OrderedDict

@csrf_exempt
def addData(request):
    response = ''
    current_id = -1
    if request.POST['data']:
        data = request.POST['data']
        p = Parser(data)
        current_id = p.parse()
        if current_id == -1:
           response = HttpResponse("The size of the file is too big.")
        else:
            response = reverse_lazy('your_entry', args=( 1, current_id))
            response = ''.join(['http://' ,RequestSite(request).domain, str(response)])
    return HttpResponse("Your entry can be found here: " +response)

@csrf_exempt
def returnUrl(request, page, query):
    return HttpResponse(request.get_full_path())

def viewEntry(request,template_name, page=None, query=None):
    return HttpResponseRedirect(reverse('entry', args=(), kwargs={"items":10, "page":page, "query":query}))

@csrf_exempt
def search(request, template_name, items = None, page = None, query = None):
    if items == None and page == None and query == None:
         page = request.GET.get('page', '')
         query = request.GET.get('query', '')
         items = request.GET.get('items', '')
    if query == "" or query.isspace() or query == "all":
        query = "all"
    nested_list = Info().getSearchResult(query)
    elems = flatten(nested_list)
    no = len(elems)
    if no == 0:
        return render_to_response(template_name, {"result" :"not found"}, RequestContext(request))
    paginator = Paginator(elems, items)
    try:
        c = paginator.page(page)
    except PageNotAnInteger:
        c = paginator.page(1)
    except EmptyPage:
        c=paginator.page(paginator.num_pages)

    if c.number <= 3:
        index = 0
        end = 5
    elif paginator.num_pages - paginator.page_range.index(c.number) <= 2:
        diff = paginator.num_pages - paginator.page_range.index(c.number)
        index = paginator.page_range.index(c.number) - 5 + diff
        if index < 0:
            index = 0
        end = paginator.page_range.index(c.number) + diff
    else:
        index = paginator.page_range.index(c.number) - 2
        end = index + 5
    return render_to_response(template_name, {'details':c, 'd' : query, "no" : no, 'list' : paginator.page_range[index:end], 'items' : items}, RequestContext(request))

def searchDetails(request, template_name, pk, page = None, query = None, items = None):
    results=''
    status_code = get_object_or_404(BuildFailure, pk=pk)
    build_failure = Info().getBFDetails(status_code.id)
    template = loader.get_template(template_name)
    c = RequestContext(request,  {'details' : build_failure, 'page' : page, 'query' : query, 'items' : items})
    return HttpResponse(template.render(c))

def chart(request, template_name, key):
    data=""
    s = Statistics()
    alldata = s.chart_statistics(key)
    if (alldata == {}):
        return render_to_response(template_name, {'nochart':'No entry.'}, context_instance=RequestContext(request))

    xdata=alldata["names"]
    ydata=alldata["values"]

    dict_chart = {}
    for i in range(len(xdata)):
        dict_chart[xdata[i]] = ydata[i]
    dict_chart = OrderedDict(sorted(dict_chart.iteritems(), key=lambda (k,v): (v,k), reverse = True))
    xdata = dict_chart.keys()
    ydata = dict_chart.values()

    total = 0
    for i in range(len(ydata)):
        total += ydata[i]
    for i in range(len(ydata)):
        ydata[i] = ydata[i]/total

    if len(xdata) > 9:
        for i in range(9, len(xdata)):
            ydata[8] += ydata[i]
        for i in range(9, len(ydata)):
            ydata.pop()
            xdata.pop()
        xdata[8] = "others"

    extra_serie = {"tooltip": {"y_start": "", "y_end": "%"}}

    chartdata = {
        'x': xdata,
        'y1': ydata, 'extra1': extra_serie,}

    charttype = "multiBarHorizontalChart"
    data = {
        'charttype': charttype,
        'chartdata': chartdata}

    return render_to_response(template_name, data, context_instance=RequestContext(request))

def flatten(nested_list):
    res =  []
    for e in nested_list:
        if hasattr(e, "__iter__") and not isinstance(e, basestring):
            res.extend(flatten(e))
        else:
            res.append(e)
    return res