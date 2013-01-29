# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Instance.geo_rev'
        db.add_column(u'treemap_instance', 'geo_rev',
                      self.gf('django.db.models.fields.IntegerField')(default=1),
                      keep_default=False)

        # Note that if you change the instance on a tree
        # the trigger wont fire
        # but, is there any reason you would change an instance?
        db.execute("""
CREATE OR REPLACE FUNCTION RevUpdate()
 RETURNS trigger AS
 $$
 DECLARE
   iid integer;
 BEGIN
 IF (TG_OP='INSERT') THEN
   iid = NEW.instance_id;
 ELSIF (TG_OP='UPDATE') THEN
   iid = NEW.instance_id;
 ELSIF (TG_OP='DELETE') THEN
   iid = OLD.instance_id;
 END IF;
 UPDATE treemap_instance SET geo_rev=geo_rev+1 WHERE id=iid ;
 Return NEW;
 END;
 $$
 LANGUAGE 'plpgsql' VOLATILE;

CREATE TRIGGER RevInsertTrigger
AFTER INSERT
ON treemap_tree
FOR EACH ROW
WHEN (NEW.the_geom_webmercator IS NOT NULL)
EXECUTE PROCEDURE RevUpdate ();

CREATE TRIGGER RevUpdateTrigger
AFTER UPDATE OF the_geom_webmercator
ON treemap_tree
FOR EACH ROW
EXECUTE PROCEDURE RevUpdate ();

CREATE TRIGGER RevDeleteTrigger
AFTER DELETE
ON treemap_tree
FOR EACH ROW
EXECUTE PROCEDURE RevUpdate ();
""")
                   


    def backwards(self, orm):
        # Deleting field 'Instance.geo_rev'
        db.delete_column(u'treemap_instance', 'geo_rev')
        
        db.execute("""
DROP TRIGGER RevInsertTrigger ON treemap_tree;
DROP TRIGGER RevUpdateTrigger ON treemap_tree;
DROP TRIGGER RevDeleteTrigger ON treemap_tree;
DROP FUNCTION RevUpdate();
""");


    models = {
        u'treemap.instance': {
            'Meta': {'object_name': 'Instance'},
            'geo_rev': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'treemap.tree': {
            'Meta': {'object_name': 'Tree'},
            'geom': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857', 'db_column': "'the_geom_webmercator'"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"})
        }
    }

    complete_apps = ['treemap']
