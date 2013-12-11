# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
from django.contrib.gis.geos import Polygon, MultiPolygon

class Migration(DataMigration):

    def forwards(self, orm):
        region_codes = [r['code'] for r in
                        orm.ITreeRegion.objects.values('code').distinct()]
        regions = {}

        for code in region_codes:
            # Make a single multipolygon using polygons from all rows for code
            rows = orm.ITreeRegion.objects.filter(code=code)
            polygons = [Polygon(*row.geometry.coords[0]) for row in rows]
            multi = MultiPolygon(polygons)
            regions[code] = multi

            # Make sure area didn't change
            area = reduce(lambda sum, p: sum + p.area, polygons, 0)
            if area != multi.area:
                raise Exception('Area of multipolygon is incorrect')

        orm.ITreeRegion.objects.all().delete()

        for code in region_codes:
            orm.ITreeRegion(code=code, geometry=regions[code]).save()


    def backwards(self, orm):
        regions = {}
        for region in orm.ITreeRegion.objects.all():
            multi = region.geometry
            polygons = [Polygon(*rings) for rings in multi.coords]
            regions[region.code] = polygons

            # Make sure area didn't change
            area = reduce(lambda sum, p: sum + p.area, polygons, 0)
            if area != multi.area:
                raise Exception('Area of multipolygon is incorrect')

        orm.ITreeRegion.objects.all().delete()

        for code in regions:
            for polygon in regions[code]:
                geom = MultiPolygon(polygon)
                orm.ITreeRegion(code=code, geometry=geom).save()


    models = {
        u'ecobenefits.itreeregion': {
            'Meta': {'object_name': 'ITreeRegion'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'geometry': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['ecobenefits']
    symmetrical = True
