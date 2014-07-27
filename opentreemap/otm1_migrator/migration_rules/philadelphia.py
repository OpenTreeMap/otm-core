from otm1_migrator.migration_rules.standard_otm1 import MIGRATION_RULES

SORT_ORDER_INDEX = {
    'Bucks': 3,
    'Burlington': 4,
    'Camden': 5,
    'Chester': 6,
    'Delaware': 7,
    'Gloucester': 8,
    'Kent': 9,
    'Mercer': 10,
    'Montgomery': 11,
    'New Castle': 12,
    'Salem': 13,
    'Sussex': 14,
}


def mutate_boundary(boundary_obj, otm1_fields):
    if ((boundary_obj.name.find('County') != -1
         or boundary_obj.name == 'Philadelphia')):
        boundary_obj.category = 'County'
        boundary_obj.sort_order = 1
    elif otm1_fields['county'] == 'Philadelphia':
        boundary_obj.category = 'Philadelphia Neighborhood'
        boundary_obj.sort_order = 2
    else:
        county = otm1_fields['county']
        boundary_obj.category = county + ' Township'
        boundary_obj.sort_order = SORT_ORDER_INDEX[county]

MIGRATION_RULES['boundary']['record_mutators'] = [mutate_boundary]
