"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    BU = require('treemap/baconUtils'),
    U = require('treemap/utility'),
    _ = require('lodash'),
    FH = require('treemap/fieldHelpers'),
    console = require('console-browserify'),
    editableForm = require('treemap/editableForm'),

    eventsLandingInEditMode = [editableForm.editStartAction, 'save:start', 'save:error'],
    eventsLandingInDisplayMode = ['idle', 'save:ok', 'cancel'];

exports.init = function(options) {
    var updateUrl = options.updateUrl,
        section = options.section || 'body',
        form = options.form || section + ' form',
        $section = $(section),
        $edit = options.edit ? $(options.edit) : $section.find('.editBtn'),
        $save = options.save ? $(options.save) : $section.find('.saveBtn'),
        $cancel = options.cancel ? $(options.cancel) : $section.find('.cancelBtn'),
        $spinner = options.spinner ? $(options.spinner) : $section.find('.spinner'),
        displayFields = options.displayFields || section + ' [data-class="display"]',
        editFields = options.editFields || section + ' [data-class="edit"]',
        validationFields = options.validationFields || section + ' [data-class="error"]',
        globalErrorSection = options.globalErrorSection,
        errorCallback = options.errorCallback || $.noop,
        onSaveBefore = options.onSaveBefore || _.identity,
        onSaveAfter = options.onSaveAfter || _.identity,

        showSavePending = function (saveIsPending) {
            $spinner.toggle(saveIsPending);
            $save.prop('disabled', saveIsPending);
            $cancel.prop('disabled', saveIsPending);
        },

        editStream = $edit.asEventStream('click').map(editableForm.editStartAction),
        saveStream = (options.saveStream || $save.asEventStream('click'))
            .doAction(showSavePending, true)
            .map('save:start'),
        externalCancelStream = BU.triggeredObjectStream('cancel'),
        cancelStream = $cancel.asEventStream('click').map('cancel'),
        actionStream = new Bacon.Bus(),

        editForm = editableForm.init(options),

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

                headers = _.compact(headers);

                data[name] =
                    _.map($table.find('tr[data-value-id]').toArray(), function(row) {
                        var $row = $(row),
                            $tds = $row.find('td'),
                            id = $row.attr('data-value-id'),

                            rowData = _.object(headers, $tds
                                        .map(function() {
                                            return $.trim($(this).attr('data-value'));
                                        }));
                        if (! _.isEmpty(id)) {
                            rowData.id = id;
                        }
                        return rowData;
                    });
            });

            onSaveBefore(data);
            return data;
        },

        update = function(data) {
            var stream = Bacon.fromPromise($.ajax({
                url: updateUrl,
                type: 'PUT',
                contentType: "application/json",
                data: JSON.stringify(data)
            }));
            stream.onValue(onSaveAfter);
            return stream;
        },

        showGlobalErrors = function (errors) {
            var $globalErrorSection = $(globalErrorSection);

            if ($globalErrorSection.length > 0) {
                $globalErrorSection.html(errors.join(','));
                $globalErrorSection.show();
            } else {
                console.log('Global error returned from server, ' +
                            'but no dom element bound from client.',
                            errors);
            }
        },

        showValidationErrorsInline = function (errors) {
            $(validationFields).not(globalErrorSection).each(function() {
                $(this).html('');
            });
            _.each(errors, function (errorList, fieldName) {
                var $field = FH.getField($(validationFields), fieldName);

                if ($field.length > 0) {
                    $field.html(errorList.join(','));
                    $field.show();
                } else {
                    console.log('Field error returned from server, ' +
                                'but no dom element bound from client.',
                                fieldName, errorList);
                }
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
                showSavePending(false);
                var result = ('responseJSON' in e) ? e.responseJSON : {};
                if ('error' in result) {
                    U.warnDeprecatedErrorMessage(result);
                    result.unstructuredError = result.error;
                }
                if (!('unstructuredError' in result)) {
                    // Make sure there's an 'unstructuredError' property
                    // we look for it in the stream that responds to this.
                    // Give it the error object to help with debugging.
                    result.unstructuredError = e;
                }
                return result;
            }),

        saveOkStream = responseStream.map(function(responseData) {
            showSavePending(false);
            return {
                formData: getDataToSave(),
                responseData: responseData
            };
        }),

        validationErrorsStream = responseErrorStream
            .filter('.fieldErrors')
            .map('.fieldErrors'),

        globalErrorsStream = responseErrorStream
            .filter('.globalErrors')
            .map('.globalErrors'),

        unhandledErrorStream = responseErrorStream
            .filter(R.and(BU.isPropertyUndefined('fieldErrors'),
                          BU.isPropertyUndefined('globalErrors')))
            .map('.unstructuredError'),

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
    actionStream.onValue(editForm.hideAndShowElements, editFields, eventsLandingInEditMode);
    actionStream.onValue(editForm.hideAndShowElements, displayFields, eventsLandingInDisplayMode);
    actionStream.onValue(editForm.hideAndShowElements, validationFields, ['save:error']);

    saveOKFormDataStream.onValue(editForm.formFieldsToDisplayValues);

    globalErrorsStream.onValue(showGlobalErrors);
    validationErrorsStream.onValue(showValidationErrorsInline);

    unhandledErrorStream.onValue(errorCallback);
    unhandledErrorStream.onValue(logError);

    editStartStream.onValue(editForm.displayValuesToFormFields);
    editStartStream.onValue(showCollectionUdfs);

    eventsLandingInDisplayModeStream.onValue(resetCollectionUdfs);

    return {
        // immutable access to all actions
        actionStream: actionStream.map(_.identity),
        cancel: externalCancelStream.trigger,
        saveOkStream: saveOkStream,
        cancelStream: cancelStream,
        inEditModeProperty: inEditModeProperty,
        showGlobalErrors: showGlobalErrors,
        showValidationErrorsInline: showValidationErrorsInline,
        getDataToSave: getDataToSave,
        setUpdateUrl: function (url) { updateUrl = url; }
    };
};
