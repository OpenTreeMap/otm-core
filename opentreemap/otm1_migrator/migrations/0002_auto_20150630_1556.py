# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0001_initial'),
        ('otm1_migrator', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='otm1userrelic',
            name='instance',
            field=models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='otm1userrelic',
            name='migration_event',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='otm1_migrator.MigrationEvent', null=True),
        ),
        migrations.AddField(
            model_name='otm1modelrelic',
            name='instance',
            field=models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='otm1modelrelic',
            name='migration_event',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='otm1_migrator.MigrationEvent', null=True),
        ),
        migrations.AddField(
            model_name='otm1commentrelic',
            name='instance',
            field=models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='otm1commentrelic',
            name='migration_event',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='otm1_migrator.MigrationEvent', null=True),
        ),
        migrations.AlterUniqueTogether(
            name='otm1userrelic',
            unique_together=set([('otm2_model_name', 'otm1_model_id', 'instance')]),
        ),
        migrations.AlterUniqueTogether(
            name='otm1modelrelic',
            unique_together=set([('otm2_model_name', 'otm1_model_id', 'instance')]),
        ),
        migrations.AlterUniqueTogether(
            name='otm1commentrelic',
            unique_together=set([('otm2_model_name', 'otm1_model_id', 'instance')]),
        ),
    ]
