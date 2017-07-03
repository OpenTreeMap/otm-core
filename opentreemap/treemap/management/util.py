# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from otm_comments.models import EnhancedThreadedComment

from importer.models import TreeImportRow

from treemap.models import (Instance, User, Tree, Role, InstanceUser,
                            MapFeature, MapFeaturePhoto, Favorite)
from treemap.audit import add_default_permissions, Audit


class InstanceDataCommand(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--instance-url-name',
            action='store',
            dest='instance_url_name',
            help='Specify the instance to add trees to'),
        parser.add_argument(
            '-i', '--instance',
            action='store',
            type=int,
            dest='instance',
            help='Specify the instance to add trees to'),
        parser.add_argument(
            '-d', '--delete',
            action='store_true',
            dest='delete',
            default=False,
            help='Delete all previous data in the instance first')

    @transaction.atomic
    def setup_env(self, *args, **options):
        """ Create some seed data """
        if options['instance']:
            instance = Instance.objects.get(pk=options['instance'])
        elif options['instance_url_name']:
            instance = Instance.objects.get(
                url_name=options['instance_url_name'])
        else:
            raise Exception("must provide instance")

        try:
            user = User.system_user()
        except User.DoesNotExist:
            self.stdout.write('Error: Could not find a superuser to use')
            return 1

        instance_user = user.get_instance_user(instance)

        if instance_user is None:
            r = Role.objects.get_or_create(name=Role.ADMINISTRATOR,
                                           rep_thresh=0,
                                           instance=instance,
                                           default_permission_level=3)
            instance_user = InstanceUser(instance=instance,
                                         user=user,
                                         role=r[0])
            instance_user.save_with_user(user)
            self.stdout.write(
                'Added system user to instance with ADMINISTRATOR role')

        add_default_permissions(instance)

        if options.get('delete', False):
            # Can't delete through the ORM because it will pull all the data
            # into memory for signal handlers, then run out of memory and crash
            # BUT... cascading delete is not handled at the DB level, so we
            # need to delete from all related tables in the right order

            n_photo = MapFeaturePhoto.objects.filter(instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM treemap_treephoto t
                    WHERE t.mapfeaturephoto_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeaturephoto p
                         WHERE p.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM treemap_mapfeaturephoto t WHERE t.instance_id = %s',  # NOQA
                    (instance.pk,))
            self.stdout.write("Deleted %s photos" % n_photo)

            n_trees = Tree.objects.filter(instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM treemap_tree t WHERE t.instance_id = %s',
                    (instance.pk,))
            self.stdout.write("Deleted %s trees" % n_trees)

            n_favorites = Favorite.objects \
                .filter(map_feature__instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM treemap_favorite f
                    WHERE f.map_feature_id IN
                        (SELECT id
                         FROM treemap_mapfeature m
                         WHERE m.instance_id = %s)
                    """,
                    (instance.pk,))
            self.stdout.write("Deleted %s favorites" % n_favorites)

            n_comments = EnhancedThreadedComment.objects \
                .filter(instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM otm_comments_enhancedthreadedcommentflag f
                    WHERE f.comment_id IN
                        (SELECT threadedcomment_ptr_id
                         FROM otm_comments_enhancedthreadedcomment c
                         WHERE c.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM otm_comments_enhancedthreadedcomment c
                    WHERE c.instance_id = %s
                    """,
                    (instance.pk,))
            self.stdout.write("Deleted %s comments" % n_comments)

            n_rows = TreeImportRow.objects \
                .filter(plot__instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE importer_treeimportrow r
                    SET plot_id = NULL
                    WHERE r.import_event_id IN
                        (SELECT id
                         FROM importer_treeimportevent e
                         WHERE e.instance_id = %s)
                    """,
                    (instance.pk,))
            self.stdout.write("Nulled out plot in %s import rows" % n_rows)

            n_features = MapFeature.objects.filter(instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM treemap_plot p
                    WHERE p.mapfeature_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeature f
                         WHERE f.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM stormwater_bioswale b
                    WHERE b.polygonalmapfeature_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeature f
                         WHERE f.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM stormwater_raingarden b
                    WHERE b.polygonalmapfeature_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeature f
                         WHERE f.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM stormwater_rainbarrel b
                    WHERE b.mapfeature_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeature f
                         WHERE f.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM stormwater_polygonalmapfeature b
                    WHERE b.mapfeature_ptr_id IN
                        (SELECT id
                         FROM treemap_mapfeature f
                         WHERE f.instance_id = %s)
                    """,
                    (instance.pk,))
            with connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM treemap_mapfeature f WHERE f.instance_id = %s',  # NOQA
                    (instance.pk,))
            self.stdout.write("Deleted %s map features" % n_features)

            n_audits = Audit.objects.filter(instance=instance).count()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
    DELETE FROM treemap_audit a
    WHERE a.instance_id = %s
    AND a.model NOT IN
    ('InstanceUser', 'Species', 'ITreeCodeOverride', 'EnhancedInstance')
                    """,
                    (instance.pk,))
            self.stdout.write("Deleted %s audits" % n_audits)

        instance.update_revs('geo_rev', 'eco_rev', 'universal_rev')

        return instance, user
