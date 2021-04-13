# -*- coding: utf-8 -*-


from django.db import models, migrations
import treemap.audit


class Migration(migrations.Migration):

    dependencies = [
        ('threadedcomments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnhancedThreadedComment',
            fields=[
                ('threadedcomment_ptr', models.OneToOneField(on_delete=models.CASCADE, parent_link=True, auto_created=True, primary_key=True, serialize=False, to='threadedcomments.ThreadedComment')),
                ('is_archived', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=('threadedcomments.threadedcomment',),
        ),
        migrations.CreateModel(
            name='EnhancedThreadedCommentFlag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('flagged_at', models.DateTimeField(auto_now_add=True)),
                ('hidden', models.BooleanField(default=False)),
                ('comment', models.ForeignKey(on_delete=models.CASCADE, to='otm_comments.EnhancedThreadedComment')),
            ],
            bases=(models.Model, treemap.audit.Auditable),
        ),
    ]
