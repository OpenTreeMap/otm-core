from django.contrib.gis.geos import fromstr
from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.gdal.error import OGRException

from otm1_migrator.migration_rules.standard_otm1 import MIGRATION_RULES


udfs = {
    'plot': {
        'type': 'udf:Plot Type',
        'powerline_conflict_potential': 'udf:Powerlines Overhead',
        'sidewalk_damage': 'udf:Sidewalk Damage'
    },

    'tree': {
        'condition': 'udf:Tree Condition',
        'steward_user': 'udf:Tree Steward',
        'sponsor': 'udf:Sponsor'
    }
}

conversions = {
    'plot': {
        'powerline_conflict_potential': {'1': 'Yes',
                                         '2': 'No',
                                         '3': 'Unknown'},
        'type': {'1': 'Well/Pit',
                 '2': 'Median/Island',
                 '3': 'Tree Lawn',
                 '4': 'Park',
                 '5': 'Planter',
                 '6': 'Other',
                 '7': 'Yard',
                 '8': 'Natural Area'},

        'sidewalk_damage': {
            '1': 'Minor or No Damage',
            '2': 'Raised More Than 3/4 Inch'
        }
    },

    'tree': {
        'condition': {
            '1': 'Dead',
            '2': 'Critical',
            '3': 'Poor',
            '4': 'Fair',
            '5': 'Good',
            '6': 'Very Good',
            '7': 'Excellent'
        }
    }
}


for model in {'plot', 'tree'}:
    MIGRATION_RULES[model]['removed_fields'] -= set(udfs[model].keys())

    for otm1name, otm2name in udfs[model].iteritems():
        rules_for_model = MIGRATION_RULES[model]

        udfs_fields = rules_for_model['renamed_fields']
        udfs_fields[otm1name] = otm2name

        if otm1name in conversions[model]:
            if 'value_transformers' not in rules_for_model:
                rules_for_model['value_transformers'] = {}
# sd specific fields to drop in otm2
MIGRATION_RULES['plot']['removed_fields'] |= {'sunset_zone', 'district'}

            value_transf = rules_for_model['value_transformers']
            value_transf[otm1name] = conversions[model][otm1name].get
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
