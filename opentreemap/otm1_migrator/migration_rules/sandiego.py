from django.contrib.gis.geos import fromstr
from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.gdal.error import OGRException

from otm1_migrator.migration_rules.standard_otm1 import MIGRATION_RULES


UDFS = {
    'plot': {
        'type': {
            'udf.name': 'Plot Type',
            'udf.choices': ['Well/Pit', 'Median/Island', 'Tree Lawn',
                            'Park', 'Planter', 'Other', 'Yard',
                            'Natural Area']
        },
        'powerline_conflict_potential': {
            'udf.name': 'Powerlines Overhead',
            'udf.choices': ['Yes', 'No', 'Unknown']
        },
        'sidewalk_damage': {
            'udf.name': 'Sidewalk Damage',
            'udf.choices': ['Minor or No Damage', 'Raised More Than 3/4 Inch']
        }
    },
    'tree': {
        'steward_user': {'field': 'udf:Tree Steward'},
        'sponsor': {'field': 'udf:Sponsor'},
        'condition': {
            'udf.name': 'Tree Condition',
            'udf.choices': ['Dead', 'Critical', 'Poor',
                            'Fair', 'Good',
                            'Very Good', 'Excellent']
        }
    }
}


# sd specific fields to drop in otm2
MIGRATION_RULES['plot']['removed_fields'] |= {'sunset_zone', 'district'}

# override this transformer because it's not desired for sd
MIGRATION_RULES['species']['value_transformers']['native_status'] = None


def transform_geometry(geometry_wkt):
    """
    Some records in the SD database are stored with a different srid. Fix them.
    """
    geom = fromstr(geometry_wkt, srid=4326)
    try:
        geom.transform(SpatialReference(3857), clone=True)
        return geom
    except OGRException:
        # make sure 102646 is in the db:
        # http://spatialreference.org/ref/esri/102646/
        bad_geom = fromstr(geometry_wkt, srid=102646)
        return bad_geom.transform(SpatialReference(4326), clone=True)

MIGRATION_RULES['plot']['value_transformers']['geometry'] = transform_geometry
