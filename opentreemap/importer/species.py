# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.db import transaction

from treemap.models import (Species, ITreeCodeOverride, ITreeRegion, User)
from treemap.species import species_for_scientific_name
from treemap.species.codes import (has_itree_code, all_itree_region_codes,
                                   all_itree_codes)

from importer.models import GenericImportEvent, GenericImportRow
from importer import fields
from importer import errors


class SpeciesImportEvent(GenericImportEvent):
    """
    A TreeImportEvent represents an attempt to upload a csv containing
    species information
    """

    max_diameter_conversion_factor = models.FloatField(default=1.0)
    max_tree_height_conversion_factor = models.FloatField(default=1.0)

    def __init__(self, *args, **kwargs):
        super(SpeciesImportEvent, self).__init__(*args, **kwargs)
        self.all_region_codes = all_itree_region_codes()
        self.all_itree_codes = all_itree_codes()
        self.instance_region_codes = self.instance.itree_region_codes()

    def create_row(self, *args, **kwargs):
        return SpeciesImportRow.objects.create(*args, **kwargs)

    def row_set(self):
        return self.speciesimportrow_set

    def __unicode__(self):
        return u"Species Import #%s" % self.pk

    def status_summary(self):
        if self.status == GenericImportEvent.CREATING:
            return "Creating Species Records"
        else:
            return super(SpeciesImportEvent, self).status_summary()

    def validate_main_file(self):
        """
        Make sure the imported file has rows and valid columns
        """
        def validate(input_fields):
            req = {fields.species.GENUS, fields.species.COMMON_NAME}

            req -= input_fields
            if req:
                return errors.MISSING_SPECIES_FIELDS
        return self._validate_main_file(self.rows(),
                                        fields.species.ALL, validate)


class SpeciesImportRow(GenericImportRow):

    SPECIES_MAP = {
        'genus': fields.species.GENUS,
        'species': fields.species.SPECIES,
        'cultivar': fields.species.CULTIVAR,
        'other_part_of_name': fields.species.OTHER_PART_OF_NAME,
        'common_name': fields.species.COMMON_NAME,
        'is_native': fields.species.IS_NATIVE,
        'gender': fields.species.GENDER,
        'flowering_period': fields.species.FLOWERING_PERIOD,
        'fruit_or_nut_period': fields.species.FRUIT_OR_NUT_PERIOD,
        'fall_conspicuous': fields.species.FALL_CONSPICUOUS,
        'flower_conspicuous': fields.species.FLOWER_CONSPICUOUS,
        'palatable_human': fields.species.PALATABLE_HUMAN,
        'has_wildlife_value': fields.species.HAS_WILDLIFE_VALUE,
        'fact_sheet_url': fields.species.FACT_SHEET_URL,
        'plant_guide_url': fields.species.PLANT_GUIDE_URL,
        'max_diameter': fields.species.MAX_DIAMETER,
        'max_height': fields.species.MAX_HEIGHT,
        'id': fields.species.ID
    }

    # Species reference
    species = models.ForeignKey(Species, null=True, blank=True)
    merged = models.BooleanField(default=False)

    import_event = models.ForeignKey(SpeciesImportEvent)

    def diff_from_species(self, species):
        """ Compute how this row is different from the given species.

        The result is a json dict with field names:
        { '<field name>': ['<species value>', '<row value>'] }

        Note that you can't *remove* data with species import.

        If the returned dictionary is empty, importing this
        row will (essentially) be a nop.

        This should only be called after a verify because it
        uses cleaned data.
        """
        #TODO: Test me
        if species is None:
            return {}

        data = self.cleaned
        result = {}
        for (model_key, row_key) in SpeciesImportRow.SPECIES_MAP.iteritems():
            row_data = data.get(row_key, None)
            model_data = getattr(species, model_key)

            if row_data and row_data != model_data:
                result[row_key] = (model_data, row_data)

        # Always include the ID (so the client can use it)
        result['id'] = (species.pk, None)

        # Compare i-Tree codes
        key = fields.species.ITREE_PAIRS
        if key in data:
            row_itree_pairs = data[key]
            model_itree_pairs = [(species.get_itree_code(region), region)
                                 for (_, region) in row_itree_pairs]
            if row_itree_pairs != model_itree_pairs:
                result[key] = (model_itree_pairs, row_itree_pairs)

        return result

    @property
    def model_fields(self):
        return fields.species

    def validate_species(self):
        # Note we handle multiple matches only for edge cases like
        # genus='Prunus' (species/genus/other blank), which matches
        # both 'Plum' and 'Cherry'

        genus = self.datadict.get(fields.species.GENUS, '')
        species = self.datadict.get(fields.species.SPECIES, '')
        cultivar = self.datadict.get(fields.species.CULTIVAR, '')
        other_part = self.datadict.get(fields.species.OTHER_PART_OF_NAME, '')

        self.cleaned[fields.species.GENUS] = genus
        self.cleaned[fields.species.SPECIES] = species
        self.cleaned[fields.species.CULTIVAR] = cultivar
        self.cleaned[fields.species.OTHER_PART_OF_NAME] = other_part

        if genus != '' or species != '' or cultivar != '' or other_part != '':
            matching_species = Species.objects \
                .filter(genus__iexact=genus) \
                .filter(species__iexact=species) \
                .filter(cultivar__iexact=cultivar) \
                .filter(other_part_of_name__iexact=other_part)

            self.cleaned[fields.species.POSSIBLE_MATCHES] \
                |= {s.pk for s in matching_species}

    def validate_usda_code(self):
        # Look for an OTM code matching the USDA code.
        # They won't match if there's a cultivar, but it might help
        # if file's USDA codes are better than its scientific names.
        usda_code = self.datadict.get(fields.species.USDA_SYMBOL, None)
        if usda_code:
            matching_species = Species.objects.filter(otm_code=usda_code)

            self.cleaned[fields.species.POSSIBLE_MATCHES] \
                |= {s.pk for s in matching_species}

    def validate_required_fields(self):
        req = {fields.species.GENUS, fields.species.COMMON_NAME}

        for field in req:
            value = self.cleaned.get(field, None)
            if not value:
                self.append_error(errors.MISSING_FIELD, field)

    def validate_itree_code_and_region(self, region, code):
        error = None
        if region not in self.import_event.all_region_codes:
            error = errors.INVALID_ITREE_REGION

        elif region not in self.import_event.instance_region_codes:
            error = errors.ITREE_REGION_NOT_IN_INSTANCE

        elif code not in self.import_event.all_itree_codes:
            error = errors.INVALID_ITREE_CODE

        elif not has_itree_code(region, code):
            error = errors.ITREE_CODE_NOT_IN_REGION

        return error

    def validate_itree_code(self, itree_code):
        region = None
        error = None
        n_regions = len(self.import_event.instance_region_codes)
        if n_regions == 0:
            error = errors.INSTANCE_HAS_NO_ITREE_REGION

        elif n_regions > 1:
            error = errors.INSTANCE_HAS_MULTIPLE_ITREE_REGIONS

        else:
            region = self.import_event.instance_region_codes[0]
            if itree_code not in self.import_event.all_itree_codes:
                error = errors.INVALID_ITREE_CODE

            elif not has_itree_code(region, itree_code):
                error = errors.ITREE_CODE_NOT_IN_REGION

        return error, region

    def validate_itree_code_field(self):
        itree_code = self.datadict.get(fields.species.ITREE_CODE)
        if not itree_code:
            return

        pairs = []
        error = None

        if ':' in itree_code:
            # Field contains region:code pairs, e.g.
            # SoCalCSMA:CEL OTHER, InlEmpCLM:CEL OTHER
            codes = [pair.split(':')
                     for pair in itree_code.split(',')]

            for region, code in codes:
                region = region.strip()
                code = code.strip()
                error = self.validate_itree_code_and_region(region, code)
                pairs.append((code, region))
                if error:
                    break

        else:
            # Field contains a single i-Tree code
            error, region = self.validate_itree_code(itree_code)
            pairs.append((itree_code, region))

        if error:
            self.append_error(error, fields.species.ITREE_CODE,
                              {'code': pairs[-1][0],
                               'region': pairs[-1][1]})
        else:
            self.cleaned[fields.species.ITREE_PAIRS] = pairs

    def validate_row(self):
        """
        Validate a row. Returns True if there were no fatal errors,
        False otherwise

        The method mutates self in two ways:
        - The 'errors' field on self will be appended to
          whenever an error is found
        - The 'cleaned' field on self will be set as fields
          get validated
        """
        # Clear errors
        self.errors = ''

        # Convert all fields to correct datatypes
        self.validate_and_convert_datatypes()

        # Check to see if this species matches any existing ones.
        # They'll be stored as a set of POSSIBLE_MATCHES
        self.cleaned[fields.species.POSSIBLE_MATCHES] = set()
        self.validate_species()
        self.validate_usda_code()

        self.validate_itree_code_field()
        self.validate_required_fields()

        # If same is set to true this is essentially a no-op
        same = False

        possible_matches = self.cleaned[fields.species.POSSIBLE_MATCHES]
        # TODO: Certain fields require this flag to be reset
        if not self.merged:
            if len(possible_matches) == 0:
                self.merged = True
            else:
                species = Species.objects.filter(pk__in=possible_matches)
                diffs = [self.diff_from_species(s) for s in species]
                # There's always a single field that has changed in the
                # diff. This is the 'id' field of the existing species,
                # which will never be the same as the None for the current
                # id.
                if all([diff.keys() == ['id'] for diff in diffs]):
                    self.merged = True
                    same = True
                    self.species = species[0]
                else:
                    diff_keys = set()

                    for diff in diffs:
                        for key in diff.keys():
                            diff_keys.add(key)

                    if len(possible_matches) > 1:
                        self.append_error(errors.TOO_MANY_SPECIES,
                                          tuple(diff_keys), tuple(diffs))
                    else:
                        self.append_error(errors.MERGE_REQ, tuple(diff_keys),
                                          diffs[0])
                        pk = list(possible_matches)[0]
                        self.species = Species.objects.get(pk=pk)

        fatal = False
        if self.has_fatal_error():
            self.status = SpeciesImportRow.ERROR
            fatal = True
        elif same:  # Nothing changed, this has been effectively added
            self.status = SpeciesImportRow.SUCCESS
        else:
            self.status = SpeciesImportRow.VERIFIED

        self.save()
        return not fatal

    @transaction.atomic
    def commit_row(self):
        # First validate
        if not self.validate_row():
            return False

        if self.status == SpeciesImportRow.SUCCESS:
            # Nothing changed!
            return True

        # Get our data
        data = self.cleaned

        species_edited = False

        # Initially grab species from row if it exists and edit it
        species = self.species

        # If not specified create a new one
        if species is None:
            species = Species(instance=self.import_event.instance)

        # Convert units
        self.convert_units(data, {
            fields.species.MAX_DIAMETER:
            self.import_event.max_diameter_conversion_factor,

            fields.species.MAX_HEIGHT:
            self.import_event.max_tree_height_conversion_factor
        })

        for modelkey, datakey in SpeciesImportRow.SPECIES_MAP.iteritems():
            importdata = data.get(datakey, None)

            if importdata is not None:
                species_edited = True
                setattr(species, modelkey, importdata)

        # Set OTM code if missing and available
        if not species.otm_code:
            species_dict = species_for_scientific_name(
                species.genus, species.species, species.cultivar,
                species.other_part_of_name)
            if species_dict:
                species_edited = True
                species.otm_code = species_dict['otm_code']

        if species_edited:
            species.save_with_system_user_bypass_auth()

        # Make i-Tree code override(s) if necessary
        if fields.species.ITREE_PAIRS in data:
            for itree_code, region_code in data[fields.species.ITREE_PAIRS]:

                if itree_code != species.get_itree_code(region_code):

                    override = ITreeCodeOverride.objects.get_or_create(
                        instance_species=species,
                        region=ITreeRegion.objects.get(code=region_code),
                    )[0]
                    override.itree_code = itree_code
                    override.save_with_user(User.system_user())

        self.species = species
        self.status = SpeciesImportRow.SUCCESS
        self.save()

        return True
