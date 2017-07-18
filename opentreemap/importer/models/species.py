# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import itertools

from collections import OrderedDict

from django.contrib.gis.db import models
from django.db import transaction
from django.utils.translation import ugettext as _

from treemap.ecobenefits import has_itree_code, all_itree_codes
from treemap.models import (Species, ITreeCodeOverride, ITreeRegion, User)
from treemap.species import species_for_scientific_name
from treemap.species.codes import all_itree_region_codes

from importer.models.base import GenericImportEvent, GenericImportRow
from importer import fields
from importer import errors


class SpeciesImportEvent(GenericImportEvent):
    """
    A TreeImportEvent represents an attempt to upload a csv containing
    species information
    """

    import_schema_version = 1  # Update if any column header name changes
    import_type = 'species'

    max_diameter_conversion_factor = models.FloatField(default=1.0)
    max_tree_height_conversion_factor = models.FloatField(default=1.0)

    class Meta:
        app_label = 'importer'

    def __init__(self, *args, **kwargs):
        super(SpeciesImportEvent, self).__init__(*args, **kwargs)
        self.all_region_codes = all_itree_region_codes()

    @property
    def instance_region_codes(self):
        if getattr(self, '_instance_region_codes', None) is None:
            self._instance_region_codes = [itr.code for itr
                                           in self.instance.itree_regions()]
        return self._instance_region_codes

    def row_set(self):
        return self.speciesimportrow_set

    def __unicode__(self):
        return _('Species Import #%s') % self.pk

    def status_description(self):
        if self.status == GenericImportEvent.CREATING:
            return "Creating Species Records"
        else:
            return super(SpeciesImportEvent, self).status_description()

    def legal_and_required_fields(self):
        return (fields.species.ALL,
                {fields.species.GENUS, fields.species.COMMON_NAME})

    def legal_and_required_fields_title_case(self):
        legal, required = self.legal_and_required_fields()
        return fields.title_case(legal), fields.title_case(required)

    def ignored_fields(self):
        return fields.species.IGNORED


class SpeciesImportRow(GenericImportRow):

    SPECIES_MAP = OrderedDict((
        ('genus', fields.species.GENUS),
        ('species', fields.species.SPECIES),
        ('cultivar', fields.species.CULTIVAR),
        ('other_part_of_name', fields.species.OTHER_PART_OF_NAME),
        ('common_name', fields.species.COMMON_NAME),
        ('is_native', fields.species.IS_NATIVE),
        ('flowering_period', fields.species.FLOWERING_PERIOD),
        ('fruit_or_nut_period', fields.species.FRUIT_OR_NUT_PERIOD),
        ('fall_conspicuous', fields.species.FALL_CONSPICUOUS),
        ('flower_conspicuous', fields.species.FLOWER_CONSPICUOUS),
        ('palatable_human', fields.species.PALATABLE_HUMAN),
        ('has_wildlife_value', fields.species.HAS_WILDLIFE_VALUE),
        ('fact_sheet_url', fields.species.FACT_SHEET_URL),
        ('plant_guide_url', fields.species.PLANT_GUIDE_URL),
        ('max_diameter', fields.species.MAX_DIAMETER),
        ('max_height', fields.species.MAX_HEIGHT),
        ('id', fields.species.ID)
    ))

    # Species reference
    species = models.ForeignKey(Species, null=True, blank=True)
    merged = models.BooleanField(default=False)

    import_event = models.ForeignKey(SpeciesImportEvent)

    class Meta:
        app_label = 'importer'

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
        diffs = {}
        for (model_key, row_key) in SpeciesImportRow.SPECIES_MAP.iteritems():
            row_data = data.get(row_key, None)
            model_data = getattr(species, model_key)

            # Note if row_data == False we want row_has_value == True
            row_has_value = row_data is not None and row_data != ''

            if row_has_value:
                if row_key in fields.species.STRING_FIELDS:
                    is_different = row_data.lower() != model_data.lower()
                else:
                    is_different = row_data != model_data
                if is_different:
                    diffs[row_key] = (model_data, row_data)

        # Always include the ID (so the client can use it)
        diffs['id'] = (species.pk, None)

        # Compare i-Tree codes
        key = fields.species.ITREE_PAIRS
        if key in data:
            row_itree_pairs = data[key]
            model_itree_pairs = [(region, species.get_itree_code(region))
                                 for (region, __) in row_itree_pairs]
            if row_itree_pairs != model_itree_pairs:
                diffs[fields.species.ITREE_CODE] = (
                    self._itree_pairs_to_string(model_itree_pairs),
                    self._itree_pairs_to_string(row_itree_pairs))

        return diffs

    def _itree_pairs_to_string(self, pairs):
        # [('SoCalCSMA', 'CEL OTHER'), ('InlEmpCLM', 'CEL OTHER')]
        #     -> "SoCalCSMA:CEL OTHER,InlEmpCLM:CEL OTHER"
        # [('SoCalCSMA', None)] -> ''
        if pairs:
            string = ','.join([':'.join(pair) for pair in pairs if all(pair)])
            return string
        else:
            return ''

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

        if genus != '' or species != '' or cultivar != '' or other_part != '':
            matching_species = Species.objects.filter(
                instance_id=self.import_event.instance_id,
                genus__iexact=genus,
                species__iexact=species,
                cultivar__iexact=cultivar,
                other_part_of_name__iexact=other_part)

            if matching_species.count() > 1:
                # Try using row's common name to disambiguate. Note that it
                # might not match (and so require a merge) (which is why we
                # didn't use it above).
                common_name = self.datadict.get(fields.species.COMMON_NAME, '')
                match_common_name = matching_species.filter(
                    common_name__iexact=common_name)
                if match_common_name.count() == 1:
                    matching_species = match_common_name

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

        elif code not in all_itree_codes():
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
            if itree_code not in all_itree_codes():
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
                pairs.append((region, code))
                if error:
                    break

        else:
            # Field contains a single i-Tree code
            error, region = self.validate_itree_code(itree_code)
            pairs.append((region, itree_code))

        if error:
            self.append_error(error, fields.species.ITREE_CODE,
                              {'region': pairs[-1][0],
                               'code': pairs[-1][1]})
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

        self.validate_itree_code_field()
        self.validate_required_fields()

        identical_to_existing = False
        if not self.merged:
            identical_to_existing = self._prepare_merge_data()

        fatal = False
        if self.has_fatal_error():
            # User needs to resolve one or more errors for this row
            self.status = SpeciesImportRow.ERROR
            fatal = True

        elif identical_to_existing:
            # We will ignore this row and consider it added
            self.status = SpeciesImportRow.SUCCESS

        else:
            # This row is either ready to add or requires a merge
            self.status = SpeciesImportRow.VERIFIED

        self.save()
        return not fatal

    def _prepare_merge_data(self):
        identical_to_existing = False
        possible_matches = self.cleaned[fields.species.POSSIBLE_MATCHES]

        if len(possible_matches) == 0:
            self.merged = True
        else:
            species = Species.objects.filter(pk__in=possible_matches)
            diffs = [self.diff_from_species(s) for s in species]

            if all(diff.keys() == ['id'] for diff in diffs):
                # Imported data differs only in ID field (None vs. something)
                identical_to_existing = True
                self.merged = True

            else:
                # Filter out diffs whose "model value" is empty
                filtered_diffs = [{k: v for k, v in diff.iteritems()
                                   if v[0] is not None and v[0] != ''}
                                  for diff in diffs]

                diff_keys = [diff.keys() for diff in filtered_diffs]
                diff_keys = set(itertools.chain(*diff_keys))
                diff_keys.remove('id')

                if len(diff_keys) == 0:
                    # All diffs (except id) are with empty model fields,
                    # so the row can be merged without user input
                    self.merged = True
                else:
                    # Store diffs for user-directed merge
                    self.append_error(errors.MERGE_REQUIRED,
                                      tuple(diff_keys), filtered_diffs)

            if len(possible_matches) == 1:
                self.species = species[0]

        return identical_to_existing

    @transaction.atomic
    def commit_row(self):
        is_valid = self.validate_row()

        if not is_valid or not self.merged:
            return  # not ready to commit

        if self.status == SpeciesImportRow.SUCCESS:
            return  # nothing changed so no need to commit

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
            for region_code, itree_code in data[fields.species.ITREE_PAIRS]:

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
