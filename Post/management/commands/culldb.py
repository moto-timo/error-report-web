# SPDX-License-Identifier: MIT
#
# error-reporting-tool -  culldb
#
# Copyright (C) 2015 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

# Create your views here.
# vi: tabstop=8 expandtab shiftwidth=4 softtabstop=4

from django.core.management.base import BaseCommand
from Post.models import Build
import time
import sys

class Command(BaseCommand):
    help = 'Culls the database to size in rows'

    def add_arguments(self, parser):
        parser.add_argument('size', nargs='?', type=int,
                            help='Number of builds to keep')
        parser.add_argument('-i',
                            '--info',
                            action="store_true",
                            help='Show the current database size')

    def handle(self, *args, **options):
        count = Build.objects.count()

        if options['info']:
            print("Current builds table size: %d" % Build.objects.count())
            return

        if options['size'] is not None:
            new_size = options['size']

            num_to_delete = count - new_size
            print("\nReducing the database size to %d which will DELETE %d rows" % (new_size, num_to_delete))
            i = 1
            while i != 0:
                i = i-1
                print('Ctrl+c TO CANCEL. Executing in... %d \r' % i, end='')
                sys.stdout.flush()
                time.sleep(1)

            q = Build.objects.all()[:num_to_delete].values_list('pk',
                                                                flat=True)
            Build.objects.filter(pk__in=list(q)).delete()
