"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    FH = require('treemap/lib/fieldHelpers.js'),
    getDatum = require('treemap/lib/otmTypeahead.js').getDatum;

// Placed onto the jquery object
require('bootstrap-datepicker');
require('bootstrap-multiselect');

// Boolean fields values are provided as "True" and "False"
// from the server-side template tags as well as in this module.
// In order to provide custom values for these fields, this function
// can be run after writing a value to the boolean field, it will
// comb through the provided data attributes to see if custom text
// is provided.
//
// To make a field/element function with customizable boolean labels:
// * specify the data-bool-true-text attribute on the element
// * specify the data-bool-false-text attribute on the element
function getBooleanFieldText (boolField, boolText) {
    var $boolField = $(boolField),
        attributes = {True: 'data-bool-true-text',
                      False: 'data-bool-false-text'},
        attribute = attributes[boolText];

    // .is() is the recommended way of doing 'hasattr'
    return $boolField.is("[" + attribute + "]") ?
        $boolField.attr(attribute) : boolText;
}

exports.editStartAction = 'edit:start';

exports.init = function(options) {
    var displayFields = options.displayFields || '[data-class="display"]',
        editFields = options.editFields || '[data-class="edit"]',

        displayValuesToTypeahead = function() {
            $('[data-typeahead-restore]').each(function(index, el) {
                var field = $(el).attr('data-typeahead-restore');
                if (field) {
                    $('input[name="' + field + '"]').trigger('restore', $(el).val());
                }
            });
        },

        displayValuesToFormFields = function() {
            $(displayFields).each(function(index, el) {
                var $el = $(el),
                    field = $el.attr('data-field'),
                    value = $el.attr('data-value'),
                    $input;

                if (field && $el.is('[data-value]')) {
                    $input = FH.getSerializableField($(editFields), field);
                    if ($input.is('[type="checkbox"]')) {
                        $input.prop('checked', value == "True");
                    }
                    else if ($input.is('[data-date-format]')) {
                        FH.applyDateToDatepicker($input, value);
                    } else if ($input.is('select[multiple]')) {
                        $input.val(JSON.parse(value));
                        $input.multiselect('refresh');
                    } else {
                        $input.val(value);
                    }
                }
            });
            displayValuesToTypeahead();
        },

        typeaheadToDisplayValues = function() {
            $('[data-typeahead-input]').each(function(index, el) {
                var datum = getDatum($(el)),
                    field = $(el).attr('data-typeahead-input');
                if (typeof datum != "undefined") {
                    $('[data-typeahead-restore="' + field + '"]').each(function(index, el) {
                        $(el).val(datum[$(el).attr('data-datum')]);
                    });
                    $('[data-typeahead="' + field + '"]').each(function(index, el) {
                        $(el).html(datum[$(el).attr('data-datum')]);
                    });
                }
            });
        },

        formFieldsToDisplayValues = function() {
            $(editFields).each(function(index, el){
                var field = $(el).attr('data-field'),
                    $input, value, display, digits, units,
                    displayValue, displayMap;

                // if the edit field has a data-field property,
                // look for a corresponding display value and if
                // found, populate the display value
                if ($(el).is('[data-field]')) {
                    display = FH.getField($(displayFields), field);

                    if ($(display).is('[data-value]')) {
                        $input = FH.getSerializableField($(editFields), field);
                        if ($input.is('[type="checkbox"]')) {
                            // To set a custom display value, use these data attributes:
                            // - data-bool-true-text
                            // - data-bool-false-text
                            value = $input.is(':checked') ? "True" : "False";
                        } else if ($input.is('[data-date-format]')) {
                            value = FH.getTimestampFromDatepicker($input);
                        } else if ($input.is('select[multiple]')) {
                            value = JSON.stringify($input.val());
                        } else if ($input.is('[type="radio"]')) {
                            $input = $input.filter(':checked');
                            value = $input.attr('data-value');
                        } else {
                            value = $input.val();
                        }

                        $(display).attr('data-value', value);
                        displayValue = value;

                        if ($input.is('select[multiple]')) {
                            FH.renderMultiChoices($(display));
                            return;
                        } else if ($input.is('select')) {
                            // Use dropdown text (not value) as display value
                            displayValue = $input.find('option:selected').text();
                        } else if ($input.is('[type="checkbox"]')) {
                            displayValue = getBooleanFieldText(display, value);
                        } else if (value && $input.is('[data-date-format]')) {
                            displayValue = $input.val();
                        } else if ($input.is('[type="radio"]')) {
                            if ($(display).is('[data-display-map]')) {
                                displayMap = JSON.parse($(display).attr('data-display-map'));
                                if (displayMap[displayValue]) {
                                    displayValue = displayMap[displayValue];
                                }
                            }
                        } else if (value) {
                            digits = $(display).data('digits');
                            if (digits) {
                                displayValue = parseFloat(value).toFixed(digits);
                            }
                            units = $(display).data('units');
                            if (units) {
                                displayValue = value + ' ' + units;
                            }
                        }
                        $(display).text(displayValue);
                    }
                }
            });
            typeaheadToDisplayValues();
        },

        hideAndShowElements = function (fields, actions, action) {
            if (_.includes(actions, action)) {
                $(fields).show();
            } else {
                if (action === exports.editStartAction) {
                    // always hide the applicable runmode buttons
                    $(fields).filter('.btn').hide();

                    // hide the display fields if there is a corresponding
                    // edit field to show in its place
                    _.each($(fields).filter(":not(.btn)"), function (field) {
                        var $field = $(field),
                            $edit = FH.getField($(editFields),
                                                $field.attr('data-field'));

                        if ($edit.length === 1) {
                            $field.hide();
                        }

                    });

                } else {
                    $(fields).hide();
                }
            }
        };

    FH.initMultiChoice($(editFields), $(displayFields));

    return {
        displayValuesToFormFields: displayValuesToFormFields,
        formFieldsToDisplayValues: formFieldsToDisplayValues,
        hideAndShowElements: hideAndShowElements,
    };
};
