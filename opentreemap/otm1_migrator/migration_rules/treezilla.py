from otm1_migrator.data_util import MigrationException
from otm1_migrator.migration_rules.standard_otm1 import MIGRATION_RULES

from treemap.models import ITreeCodeOverride, ITreeRegion, User

TREEZILLA_ITREE_REGION_CODE = 'NoEastXXX'
METERS_TO_INCHES = 39.3701
METERS_TO_FEET = 3.28084

MIGRATION_RULES['tree']['removed_fields'].remove('tree_owner')
MIGRATION_RULES['tree']['common_fields'].add('tree_owner')

BOUNDARY_TYPES = {
    'DIS': {'name': 'District', 'sort_order': 10},
    'LBO': {'name': 'London Borough', 'sort_order': 10},
    'MTD': {'name': 'Metropolitan District', 'sort_order': 10},
    'UTA': {'name': 'Unitary Authority', 'sort_order': 10},
}


def set_boundary_fields(boundary_obj, boundary_dict):
    # The 'city' column in the Treezilla boundary table is a boundary type code
    boundary_type = BOUNDARY_TYPES.get(
        boundary_dict['fields'].get('city', None), None)
    if boundary_type is None:
        raise MigrationException("boundary_dict missing valid city value: " +
                                 str(boundary_dict))
    boundary_obj.category = boundary_type['name']
    boundary_obj.sort_order = boundary_type['sort_order']
    return boundary_obj

MIGRATION_RULES['boundary']['presave_actions'] = (MIGRATION_RULES['boundary']
                                                  .get('presave_actions', [])
                                                  + [set_boundary_fields])


def convert_tree_measurements(tree_obj, tree_dict):
    """
    Treezilla's OTM1 database stores both the tree diamater and height
    in meters. OTM2 stores diameter in inches and height in feet and
    converts on the fly to metric. Treezilla does not have any values
    in their canopy_height column.
    """
    diameter_in_meters = tree_dict['fields'].get('dbh', None)
    if diameter_in_meters is not None:
        tree_obj.diameter = diameter_in_meters * METERS_TO_INCHES

    height_in_meters = tree_dict['fields'].get('height', None)
    if height_in_meters is not None:
        tree_obj.height = height_in_meters * METERS_TO_FEET

    return tree_obj

MIGRATION_RULES['tree']['presave_actions'] = (MIGRATION_RULES['tree']
                                              .get('presave_actions', [])
                                              + [convert_tree_measurements])

# The treezilla database stores species measurement maximums in meters
MIGRATION_RULES['species']['value_transformers']['v_max_dbh'] = (
    lambda x: x * METERS_TO_INCHES if x else 10000)

MIGRATION_RULES['species']['value_transformers']['v_max_height'] = (
    lambda x: x * METERS_TO_FEET if x else 10000)


def create_override(species_obj, species_dict):
    itree_code = species_dict['fields'].get('itree_code', None)
    if not itree_code:
        raise MigrationException("species_dict missing itree_code: " +
                                 str(species_dict))
    override = ITreeCodeOverride(
        instance_species_id=species_obj.pk,
        region=ITreeRegion.objects.get(code=TREEZILLA_ITREE_REGION_CODE),
        itree_code=itree_code)
    override.save_with_user(User.system_user())
    return species_obj

MIGRATION_RULES['species']['postsave_actions'] = (MIGRATION_RULES['species']
                                                  .get('postsave_actions', [])
                                                  + [create_override])

# The choice field values were copied from the values returned by the /choices/
# endpoint of the deployed OTM1 app.
UDFS = {
    'plot': {
        'type': {
            'udf.name': 'Plot Type',
            'udf.choices': ['Residential Yard',
                            'Park',
                            'Schoolyard',
                            'Tree Pit in a Paved Area',
                            'Median',
                            'Tree Lawn or Planting Strip',
                            'Island',
                            'Raised Planter',
                            'Open/Unrestricted Area',
                            'Other']
        },
        'powerline_conflict_potential': {
            'udf.name': 'Powerlines Overhead',
            'udf.choices': ['Yes',
                            'No',
                            'Unknown']
        },
        'sidewalk_damage': {
            'udf.name': 'Sidewalk Damage',
            'udf.choices': ['Minor or No Damage',
                            'Raised More than 25 mm']
        }
    },
    'tree': {
        'sponsor': {'udf.name': 'Sponsor'},
        'tree_owner': {'udf.name': 'Owner'},
        'pests': {
            'udf.name': 'Pests',
            'udf.choices': [
                'Ash dieback (Chalara fraxiniae)',
                'Asian longhorn beetle (Anoplophora glabripennis)',
                'Bronze birch borer (Agrilus anxius)',
                'Emerald ash borer (Agrilus planipennis)',
                'Horse chestnut bleeding canker (Pseudomonas syringae pv aesculi)',  # NOQA
                'Horse chestnut leaf miner (Cameraria ohridella)',
                'Needle blight (Dothistroma septosporum)',
                'Oak processionary moth (Thaumetopoea processionea)',
                'Phytophthora alni',
                'Phytophthora austrocedrae',
                'Phytophthora kernoviae',
                'Phytophthora lateralis',
                'Phytophthora ramorum',
                'Sweet chestnut blight (Cryphonectria parasitica)']
        },
        'condition': {
            'udf.name': 'Tree Condition',
            'udf.choices': ['Dead',
                            'Critical',
                            'Poor',
                            'Fair',
                            'Good',
                            'Very Good',
                            'Excellent']
        },
        'canopy_condition': {
            'udf.name': 'Canopy Condition',
            'udf.choices': ['Full - No Gaps',
                            'Small Gaps - Up to 25% Missing',
                            'Moderate Gaps - Up to 50% Missing',
                            'Large Gaps - Up to 75% Missing',
                            'Little or None - Up to 100% Missing']
        }
    }
}
