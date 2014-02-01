"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    BU = require('treemap/baconUtils'),
    _ = require('lodash'),
    moment = require('moment'),
    FH = require('treemap/fieldHelpers'),
    getDatum = require('treemap/otmTypeahead').getDatum,
    console = require('console-browserify'),

    eventsLandingInEditMode = ['edit:start', 'save:start', 'save:error'],
    eventsLandingInDisplayMode = ['idle', 'save:ok', 'cancel'];

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(options) {
    var updateUrl = options.updateUrl,
        form = options.form,
        $edit = $(options.edit),
        $save = $(options.save),
        $cancel = $(options.cancel),
        displayFields = options.displayFields,
        editFields = options.editFields,
        validationFields = options.validationFields,
        errorCallback = options.errorCallback || $.noop,
        onSaveBefore = options.onSaveBefore || _.identity,
        editStream = $edit.asEventStream('click').map('edit:start'),
        saveStream = (options.saveStream || $save.asEventStream('click')).map('save:start'),
        externalCancelStream = BU.triggeredObjectStream('cancel'),
        cancelStream = $cancel.asEventStream('click').map('cancel'),
        actionStream = new Bacon.Bus(),

        logError = function(error) {
            console.error("Error uploading to " + updateUrl, error);
        },

        resetCollectionUdfs = function() {
            // Hide the edit row
            $("table[data-udf-id] .editrow").hide();

            // If there are no 'data' rows on a given table
            // hide the header and show the placeholder
            $("table[data-udf-id]").map(function() {
                var $table = $(this);

                // If the table has 3 rows they are:
                //
                // header, edit row (hidden), placeholder row (hidden)
                //
                // This means there is no user data, so
                // show the placeholder and hide the header
                if ($table.find('tr').length === 3) {
                    $table.find('.placeholder').show();
                    $table.find('.headerrow').hide();
                } else {
                    // We have some data rows so show the header
                    // and not the placeholder
                    $table.find('.placeholder').hide();
                    $table.find('.headerrow').show();
                }
            });
        },

        showCollectionUdfs = function() {
            // By default collection udfs have their input row
            // hidden, so show that row
            $("table[data-udf-id] .editrow").css('display', '');

            // The header row may also be hidden if there are no
            // items so show that as well
            $("table[data-udf-id] .headerrow").css('display', '');

            $("table[data-udf-id] .placeholder").css('display', 'none');
        },

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
                    $input, value, display, digits, units;

                // if the edit field has a data-field property,
                // look for a corresponding display value and if
                // found, populate the display value
                if ($(el).is('[data-field]')) {
                    display = FH.getField($(displayFields), field);

                    if ($(display).is('[data-value]')) {
                        $input = FH.getSerializableField($(editFields), field);
                        if ($input.is('[type="checkbox"]')) {
                            value = $input.is(':checked') ? "True" : "False";
                        } else if ($input.is('[data-date-format]')) {
                            value = FH.getTimestampFromDatepicker($input);
                        } else {
                            value = $input.val();
                        }
                        $(display).attr('data-value', value);
                        if ($input.is('select')) {
                            // Use dropdown text (not value) as display value
                            value = $input.find('option:selected').text();
                        } else if (value && $input.is('[data-date-format]')) {
                            value = $input.val();
                        } else if (value) {
                            digits = $(display).data('digits');
                            if (digits) {
                                value = parseFloat(value).toFixed(digits);
                            }
                            units = $(display).data('units');
                            if (units) {
                                value = value + ' ' + units;
                            }
                        }
                        $(display).html(value);
                    }
                }
            });
            typeaheadToDisplayValues();
        },

        getDataToSave = function() {
            var data = FH.formToDictionary($(form), $(editFields), $(displayFields));

            // Extract data for all rows of the collection,
            // whether entered in this session or pre-existing.
            $('table[data-udf-name]').map(function() {
                var $table = $(this);
                var name = $table.data('udf-name');

                var headers = $table.find('tr.headerrow th')
                        .map(function() {
                            return $(this).html();
                        });

                data[name] =
                    _.map($table.find('tr[data-value-id]').toArray(), function(row) {
                        return _.object(headers, $(row)
                                        .find('td')
                                        .map(function() {
                                            return $.trim($(this).html());
                                        }));
                    });
            });

            onSaveBefore(data);
            return data;
        },

        update = function(data) {
            return Bacon.fromPromise($.ajax({
                url: updateUrl,
                type: 'PUT',
                contentType: "application/json",
                data: JSON.stringify(data)
            }));
        },

        showValidationErrorsInline = function (errors) {
            $(validationFields).each(function() {
                $(this).html('');
            });
            _.each(errors, function (errorList, fieldName) {
                FH.getField($(validationFields), fieldName)
                    .html(errorList.join(','));
            });
        },

        isEditStart = function (action) {
            return action === 'edit:start';
        },

        responseStream = saveStream
            .map(getDataToSave)
            .flatMap(update),

        responseErrorStream = responseStream
            .errors()
            .mapError(function (e) {
                var result = ('responseJSON' in e) ? e.responseJSON : {};
                if (!('error' in result)) {
                    // Make sure there's an "error" property; we look for it below.
                    // Give it the error object to help with debugging.
                    result.error = e;
                }
                return result;
            }),

        saveOkStream = responseStream.map(function(responseData) {
            return {
                formData: getDataToSave(),
                responseData: responseData
            };
        }),

        hideAndShowElements = function (fields, actions, action) {
            if (_.contains(actions, action)) {
                $(fields).show();
            } else {
                if (action === 'edit:start') {
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
        },

        validationErrorsStream = responseErrorStream
            .filter('.validationErrors')
            .map('.validationErrors'),

        unhandledErrorStream = responseErrorStream
            .filter(BU.isPropertyUndefined, 'validationErrors')
            .map('.error'),

        editStartStream = actionStream.filter(isEditStart),

        inEditModeProperty = actionStream.map(function (event) {
            return _.contains(eventsLandingInEditMode, event);
        }).toProperty(),

        saveOKFormDataStream = saveOkStream.map('.formData'),

        eventsLandingInDisplayModeStream =
            actionStream.filter(_.contains, eventsLandingInDisplayMode),

        shouldBeInEditModeStream = options.shouldBeInEditModeStream || Bacon.never(),
        modeChangeStream = shouldBeInEditModeStream
            .map(function(isInEdit) {
                return isInEdit ? 'edit:start' : 'cancel';
            });

    $(editFields).find("input[data-date-format]").datepicker();

    // Prevent default form submission from clicking on buttons or pressing
    // enter. Event is delegated on window since sometimes <form>s are inserted
    // into the page via AJAX without reiniting inlineEditForm
    $(window).on('submit', form, function(event) { event.preventDefault(); });

    // Merge the major streams on the page together so that it can centrally
    // manage the cleanup of ui forms after the change in run mode
    actionStream.plug(editStream);
    actionStream.plug(saveStream);
    actionStream.plug(cancelStream);
    actionStream.plug(externalCancelStream);
    actionStream.plug(saveOkStream.map('save:ok'));
    actionStream.plug(responseErrorStream.map('save:error'));
    actionStream.plug(modeChangeStream);
    actionStream.onValue(hideAndShowElements, editFields, eventsLandingInEditMode);
    actionStream.onValue(hideAndShowElements, displayFields, eventsLandingInDisplayMode);
    actionStream.onValue(hideAndShowElements, validationFields, ['save:error']);

    saveOKFormDataStream.onValue(formFieldsToDisplayValues);

    validationErrorsStream.onValue(showValidationErrorsInline);

    unhandledErrorStream.onValue(errorCallback);
    unhandledErrorStream.onValue(logError);

    editStartStream.onValue(displayValuesToFormFields);
    editStartStream.onValue(showCollectionUdfs);

    eventsLandingInDisplayModeStream.onValue(resetCollectionUdfs);

    return {
        // immutable access to all actions
        actionStream: actionStream.map(_.identity),
        cancel: externalCancelStream.trigger,
        saveOkStream: saveOkStream,
        cancelStream: cancelStream,
        inEditModeProperty: inEditModeProperty,
        setUpdateUrl: function (url) { updateUrl = url; }
    };
};
