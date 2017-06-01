"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    BU = require('treemap/lib/baconUtils.js'),
    U = require('treemap/lib/utility.js'),
    _ = require('lodash'),
    FH = require('treemap/lib/fieldHelpers.js'),
    console = require('console-browserify'),
    editableForm = require('treemap/lib/editableForm.js'),

    eventsLandingInEditMode = [editableForm.editStartAction, 'save:start', 'save:error'],
    eventsLandingInDisplayMode = ['idle', 'save:ok', 'cancel'];

exports.init = function(options) {
    var updateUrl = options.updateUrl,
        section = options.section || 'body',
        form = options.form || section + ' form',
        $section = $(section),
        edit = options.edit || '.editBtn',
        save = options.save || '.saveBtn',
        cancel = options.cancel || '.cancelBtn',
        spinner = options.spinner || '.spinner',
        displayFields = options.displayFields || section + ' [data-class="display"]',
        editFields = options.editFields || section + ' [data-class="edit"]',
        validationFields = options.validationFields || section + ' [data-class="error"]',
        globalErrorSection = options.globalErrorSection,
        errorCallback = options.errorCallback || $.noop,
        dontUpdateOnSaveOk = options.dontUpdateOnSaveOk || false,

        showSavePending = function (saveIsPending) {
            $section.find(spinner).toggle(saveIsPending);
            $section.find(save).prop('disabled', saveIsPending);
            $section.find(cancel).prop('disabled', saveIsPending);
        },

        editStream = $section.asEventStream('click', edit).map(editableForm.editStartAction),
        saveStream = (options.saveStream || $section.asEventStream('click', save))
            .doAction(showSavePending, true)
            .map('save:start'),
        externalCancelStream = BU.triggeredObjectStream('cancel'),
        cancelStream = $section.asEventStream('click', cancel).map('cancel'),
        globalCancelStream = cancelStream.merge(externalCancelStream),

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

        getDataToSave = options.getDataToSave || function() {
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

                            rowData = _.zipObject(headers, $tds
                                        .map(function() {
                                            return $.trim($(this).attr('data-value'));
                                        }));
                        if (! _.isEmpty(id)) {
                            rowData.id = id;
                        }
                        return rowData;
                    });
            });

            return data;
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
                    $field.parents('.error').show();
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
            .flatMapLatest(function (data) {
                // onSaveBefore is a function that takes form data
                // and carries out arbitrary, potentially blocking
                // actions before allowing the save process to
                // continue.
                //
                // the return value of an onSaveBefore callback can be:
                // * null - for non-blocking side effects and mutation
                //          of the data object
                // * an eventStream - for blocking side effects,
                //                    failure cases and early exits.
                //
                // when providing an eventStream as the return value for
                // onSaveBefore, it should meet the following criteria:
                // * it should be a stream of data objects. If you are using
                //   eventStreams to block on IO, map them to the `data`
                //   object provided.
                // * it should pust a new stream value when it's ok to
                //   proceed and block until then. There is no concept
                //   of exiting, just failing to stop blocking.
                var result = options.onSaveBefore ?
                        options.onSaveBefore(data) : null;
                if (_.isNull(result) || _.isUndefined(result)) {
                    return Bacon.once(data);
                } else if (_.isObject(result) && result.hasOwnProperty('takeUntil')) {
                    return result;
                } else {
                    throw "onSaveBefore returned something other than a stream or null";
                }
            })
            .flatMap(function(data) {
                return Bacon.fromPromise($.ajax({
                    url: updateUrl,
                    type: 'PUT',
                    contentType: "application/json",
                    data: JSON.stringify(data)
                }));
            }),

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
            if (!dontUpdateOnSaveOk) {
                showSavePending(false);
            }
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
            .filter(R.both(BU.isPropertyUndefined('fieldErrors'),
                           BU.isPropertyUndefined('globalErrors')))
            .map('.unstructuredError'),

        editStartStream = actionStream.filter(isEditStart),

        inEditModeProperty = actionStream.map(function (event) {
            return _.includes(eventsLandingInEditMode, event);
        })
            .toProperty()
            .skipDuplicates(),

        saveOKFormDataStream = saveOkStream.map('.formData'),

        eventsLandingInDisplayModeStream =
            actionStream.filter(_.includes, eventsLandingInDisplayMode),

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
    // manage the cleanup of ui forms after the change in run mode.
    //
    // Note that if the user is not logged in, the buttonEnabler removes the
    // data-class attribute. In that condition, editing is impossible,
    // so avoid plugging edit related streams into the actionStream.
    // We assume that the edit element exists by the time this code is reached.
    // Ajax that retrieves html snippets containing the edit button is done
    // in response to a successful save, but that will not occur when the
    // user is not logged in.
    if ($(edit).length && $(edit).first().is('[data-class]')) {
        actionStream.plug(editStream);
        actionStream.plug(saveStream);
        actionStream.plug(cancelStream);
        actionStream.plug(externalCancelStream);
        actionStream.plug(saveOkStream.map('save:ok'));
        actionStream.plug(responseErrorStream.map('save:error'));
        actionStream.plug(modeChangeStream);
        actionStream.onValue(hideAndShowElements, editFields, eventsLandingInEditMode);
        actionStream.onValue(editForm.hideAndShowElements, validationFields, ['save:error']);
    }
    actionStream.onValue(hideAndShowElements, displayFields, eventsLandingInDisplayMode);

    function hideAndShowElements(fields, actions, action) {
        var shouldHideAndShow = !(dontUpdateOnSaveOk && action === 'save:ok');
        if (shouldHideAndShow) {
            editForm.hideAndShowElements(fields, actions, action);
        }
    }

    globalCancelStream.onValue(showSavePending, false);

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
        // TODO: audit all uses of cancelStream, external cancel, and
        // global cancel stream and merge these streams in the api
        cancelStream: cancelStream,
        globalCancelStream: globalCancelStream,
        inEditModeProperty: inEditModeProperty,
        showGlobalErrors: showGlobalErrors,
        showValidationErrorsInline: showValidationErrorsInline,
        setUpdateUrl: function (url) { updateUrl = url; }
    };
};
