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

# At the time of migration, 7 of the Tampa species did not have an i-Tree code
# defined in the species fixture. otm-legacy has a one-to-many relationship
# between the `treemap_species` table and the `treemap_resources` table via
# `treemap_species_resource` and the i-Tree code used by the eco benefit
# calculations is read from the `meta_species` column of the
# `treemap_resources` table.
#
# Rather than spend time updating the migrator to
# handle this edge case, we have opted to add a literal dictionary lookup for
# these species so we can properly calculate eco benefits for these species.
#
# The lookup table was created by running this query against the otm-legacy
# database:
#
# SELECT lower(scientific_name), meta_species
# FROM treemap_species s
# JOIN treemap_species_resource sr ON s.id = sr.species_id
# JOIN treemap_resource r ON sr.resource_id = r.id
# WHERE itree_code = '';
meta_species = {
    'phanera yunnanensis': 'BEM OTHER',
    'phoenix dactylifera': 'PEM OTHER',
    'tabebuia chrysotricha': 'BDS OTHER',
    'phoenix rupicola': 'PEM OTHER',
    'tabebuia impetiginosa': 'BDM OTHER',
    'unknown unknown': 'BDM OTHER',
    'phoenix sylvestris': 'PEM OTHER'
}


def create_override(species_obj, species_dict):
    itree_code = species_dict['fields'].get('itree_code', None)
    if not itree_code:
        sci_name = species_dict['fields'].get('scientific_name', '').lower()
        print('No itree_code for "%d: %s"' % (species_dict['pk'], sci_name))
        itree_code = meta_species.get(sci_name, '')
        print('Looked up meta species "%s"' % itree_code)
    override = ITreeCodeOverride(
        instance_species_id=species_obj.pk,
        region=ITreeRegion.objects.get(code=TAMPA_ITREE_REGION_CODE),
        itree_code=itree_code)
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
