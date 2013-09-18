"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('underscore'),
    FH = require('./fieldHelpers'),
    getDatum = require('./otmTypeahead').getDatum;

// Requiring this module handles wiring up the browserified
// baconjs to jQuery
require('./baconUtils');

var eventsLandingInEditMode = ['edit:start', 'save:start', 'save:error'],
    eventsLandingInDisplayMode = ['idle', 'save:ok', 'cancel'];

exports.init = function(options) {
    var updateUrl = options.updateUrl,
        form = options.form,
        edit = options.edit,
        save = options.save,
        cancel = options.cancel,
        displayFields = options.displayFields,
        editFields = options.editFields,
        validationFields = options.validationFields,
        onSaveBefore = options.onSaveBefore || _.identity,

        editStream = $(edit).asEventStream('click').map('edit:start'),
        saveStream = $(save).asEventStream('click').map('save:start'),
        cancelStream = $(cancel).asEventStream('click').map('cancel'),
        actionStream = new Bacon.Bus(),

        displayValuesToTypeahead = function() {
            $('[data-typeahead-restore]').each(function(index, el) {
                var field = $(el).attr('data-typeahead-restore');
                if (field) {
                    $('input[name="' + field + '"]').trigger('restore', $(el).val());
                }
            });
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

        displayValuesToFormFields = function() {
            $(displayFields).each(function(index, el) {
                var field = $(el).attr('data-field');
                var value = $(el).attr('data-value');
                var $input;
                if (field) {
                    $input = FH.getField($(editFields), field)
                                .find('input,select')
                                .first();
                    if ($input.is('[type="checkbox"]')) {
                        $input.prop('checked', value == "True");
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
                var field = $(el).attr('data-field');
                var $input, value, display;
                if ($(el).is('[data-field]')) {
                    $input = FH.getField($(editFields), field)
                        .find('input,select')
                        .first();
                    if ($input.is('[type="checkbox"]')) {
                        value = $input.is(':checked') ? "True" : "False";
                    } else {
                        value = $input.val();
                    }
                    display = FH.getField($(displayFields), field);
                    $(display).attr('data-value', value);
                    $(display).html(value);
                }
            });
            typeaheadToDisplayValues();
        },

        getDataToSave = function() {
            var data = FH.formToDictionary($(form), $(editFields));

            // Extract data for all rows of the collection,
            // whether entered in this session or pre-existing.
            $('table[data-udf-name]').map(function() {
                var $table = $(this);
                var name = $table.data('udf-name');

                var headers = $table.find('tr.headerrow td')
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
                url: exports.updateUrl,
                type: 'PUT',
                contentType: "application/json",
                data: JSON.stringify(data)
            }));
        },

        showValidationErrorsInline = function (errors) {
            _.each(errors, function (errorList, fieldName) {
                FH.getField($(validationFields), fieldName)
                    .html(errorList.join(','));
            });
        },

        isEditStart = function (action) {
            return action === 'edit:start';
        },

        isEditCancel = function (action) {
            return action === 'cancel';
        },

        responseStream = saveStream
            .map(getDataToSave)
            .flatMap(update)
            .mapError(function (e) {
                var result = ('responseJSON' in e) ? e.responseJSON : {};
                if (!('error' in result)) {
                    // Make sure there's an "error" property; we look for it below
                    result.error = "Error";
                }
                return result;
            }),

        saveOkStream = responseStream.filter(function (result) {
            return !('error' in result);
        }),

        hideAndShowElements = function (action) {
            function hideOrShow(fields, actions) {
                if (_.contains(actions, action)) {
                    $(fields).show();
                } else {
                    $(fields).hide();
                }
            }
            hideOrShow(editFields, eventsLandingInEditMode);
            hideOrShow(displayFields, eventsLandingInDisplayMode);
            hideOrShow(validationFields, ['save:error']);
        };

    saveOkStream.onValue(formFieldsToDisplayValues);

    responseStream.filter('.validationErrors')
                  .map('.validationErrors')
                  .onValue(showValidationErrorsInline);

    // TODO: Show success toast
    // TODO: Show error toast
    // TODO: Keep the details of showing toast out of
    //       this module (use EventEmitter or callbacks)

    actionStream.plug(editStream);
    actionStream.plug(saveStream);
    actionStream.plug(cancelStream);

    actionStream.plug(
        responseStream.filter('.error').map('save:error')
    );

    actionStream.plug(
        saveOkStream.map('save:ok')
    );

    actionStream.filter(isEditStart).onValue(displayValuesToFormFields);
    actionStream.filter(isEditStart).onValue(showCollectionUdfs);

    actionStream
        .filter(_.contains, eventsLandingInDisplayMode)
        .onValue(resetCollectionUdfs);

    actionStream.onValue(hideAndShowElements);

    exports.inEditModeProperty = actionStream.map(function (event) {
        return _.contains(eventsLandingInEditMode, event);
    }).toProperty(false);

    exports.saveOkStream = saveOkStream;
    exports.cancelStream = cancelStream;
    exports.updateUrl = updateUrl;
};
