# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Post', '0004_auto_20160530_1126'),
    ]

    operations = [
        migrations.AddField(
            model_name='build',
            name='ERROR_TYPE',
            field=models.CharField(default=b'R', max_length=2, choices=[(b'R', b'Recipe'), (b'C', b'Core'), (b'B', b'Bitbake selftest'), (b'O', b'OE selftest')]),
        ),
    ]
