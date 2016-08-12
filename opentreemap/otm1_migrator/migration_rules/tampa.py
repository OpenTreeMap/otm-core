from otm1_migrator.migration_rules.standard_otm1 import MIGRATION_RULES

from treemap.models import ITreeCodeOverride, ITreeRegion, User

TAMPA_ITREE_REGION_CODE = 'CenFlaXXX'

# The Tampa species fixture does not include family
MIGRATION_RULES['species']['removed_fields'].remove('family')

# The Tampa species fixtue does not include other_part_of name
MIGRATION_RULES['species']['common_fields'].remove('other_part_of_name')
MIGRATION_RULES['species']['missing_fields'].add('other_part_of_name')

# The Tampa tree fixture does not include pests or url
MIGRATION_RULES['tree']['removed_fields'].remove('pests')
MIGRATION_RULES['tree']['removed_fields'].remove('url')


def set_boundary_fields(boundary_obj, boundary_dict):
    # All Tampa boundaries are neighborhoods
    boundary_obj.category = 'Tampa Neighborhood'
    # Setting the sort order to 10 allows for inserting boudaries in the
    # future which sort before the neighborhoods
    boundary_obj.sort_order = 10
    return boundary_obj

MIGRATION_RULES['boundary']['presave_actions'] = (MIGRATION_RULES['boundary']
                                                  .get('presave_actions', [])
                                                  + [set_boundary_fields])


def create_override(species_obj, species_dict):
    override = ITreeCodeOverride(
        instance_species_id=species_obj.pk,
        region=ITreeRegion.objects.get(code=TAMPA_ITREE_REGION_CODE),
        itree_code=species_dict['fields']['itree_code'])
    override.save_with_user(User.system_user())
    return species_obj

MIGRATION_RULES['species']['postsave_actions'] = (MIGRATION_RULES['species']
                                                  .get('postsave_actions', [])
                                                  + [create_override])


UDFS = {
    'plot': {
        'type': {
            'udf.name': 'Plot Type',
            'udf.choices': ['Well or Pit', 'Median', 'Tree Lawn', 'Island'
                            'Planter', 'Open', 'Other', 'Natural Area']
        },
        'powerline_conflict_potential': {
            'udf.name': 'Powerlines Overhead',
            'udf.choices': ['Yes', 'No', 'Unknown']
        },
        'sidewalk_damage': {
            'udf.name': 'Sidewalk Damage',
            'udf.choices': ['Minor or No Damage',
                            'Raised More Than 3/4 Inch',
                            'No Sidewalk']
        }
    },
    'tree': {
        'sponsor': {'udf.name': 'Sponsor'},
        'condition': {
            'udf.name': 'Tree Condition',
            'udf.choices': ['Excellent', 'Very Good', 'Good',
                            'Fair', 'Poor', 'Critial', 'Dead',
                            'Removed']
        },
        'canopy_condition': {
            'udf.name': 'Canopy Condition',
            'udf.choices': ['Full - No Gaps',
                            'Small Gaps (up to 25% missing)',
                            'Moderate Gaps (up to 50% missing)',
                            'Large Gaps (up to 75% missing)',
                            'Little or None (up to 100% missing)']
        }
    }
}
