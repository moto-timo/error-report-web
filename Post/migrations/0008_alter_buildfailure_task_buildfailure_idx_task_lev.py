from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Post', '0007_alter_build_date_alter_build_error_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buildfailure',
            name='TASK',
            field=models.CharField(max_length=750),
        ),
        migrations.AddIndex(
            model_name='buildfailure',
            index=models.Index(fields=['TASK', 'LEV_DISTANCE'], name='idx_task_lev'),
        ),
    ]
