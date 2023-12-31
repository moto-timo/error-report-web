# SPDX-License-Identifier: MIT
#
# error-reporting-tool -  culldb
#
# Copyright (C) 2015 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

# Create your views here.
# vi: tabstop=8 expandtab shiftwidth=4 softtabstop=4

from django.core.management.base import BaseCommand, CommandError
from Post.models import Build, BuildFailure
import time
import sys

class Command(BaseCommand):
    help = 'Culls the database to size in rows'

    def add_arguments(self, parser):
        parser.add_argument("-s", "--size", action='store', type=int, default=-1)
        parser.add_argument(
            '-i',
            '--info',
            dest='info',
            action='store_true',
            help='Show the current database size')

    def handle(self, *args, **options):
        count = Build.objects.count()

        if options['info']:
            print("Current builds table size: %d" % Build.objects.count())
            return

        if options['size'] >= 0:
            try:
                new_size = int(options['size'])
            except ValueError:
                print("Not a valid size")
                return


            num_to_delete = count - new_size
            print("\nReducing the database size to %d which will DELETE %d rows" % (new_size, num_to_delete))
            countdown = 5
            try:
                while True:
                    print('Ctrl+c TO CANCEL. Executing in... %d' % countdown, end='\r'),
                    sys.stdout.flush()
                    time.sleep(1)
                    if countdown == 0:
                        break
                    countdown = countdown-1
            except KeyboardInterrupt:
                sys.exit()

            q = Build.objects.all()[:num_to_delete].values_list('pk',
                                                                flat=True)
            Build.objects.filter(pk__in=list(q)).delete()
