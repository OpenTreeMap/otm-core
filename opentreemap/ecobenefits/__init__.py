from species import CODES


def all_region_codes():
    return CODES.keys


def all_species_codes():
    return species_codes_for_regions(all_region_codes())


def species_codes_for_regions(region_codes):
    if region_codes is None:
        return None
    species_codes = []
    for region_code in region_codes:
        species_codes.extend(CODES[region_code])
    # Converting to a set removes duplicates
    return list(set(species_codes))
