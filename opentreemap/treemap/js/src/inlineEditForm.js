"use strict";

var $ = require('jquery');
var Bacon = require('baconjs');
var _ = require('underscore');
var FH = require('./fieldHelpers');

// Requiring this module handles wiring up the browserified
// baconjs to jQuery
require('./baconUtils');

exports.init = function(options) {
    var updateUrl = options.updateUrl,
        form = options.form,
        edit = options.edit,
        save = options.save,
        cancel = options.cancel,
        displayFields = options.displayFields,
        editFields = options.editFields,
        validationFields = options.validationFields,

        editStream = $(edit).asEventStream('click').map('edit:start'),
        saveStream = $(save).asEventStream('click').map('save:start'),
        cancelStream = $(cancel).asEventStream('click').map('cancel'),
        actionStream = new Bacon.Bus(),

        actionToCssDisplay = function(actions, action) {
            return _.contains(actions, action) ? '' : 'none';
        },

        actionToEditFieldCssDisplay = _.partial(actionToCssDisplay,
            ['edit:start', 'save:start', 'save:error']),

        actionToDisplayFieldCssDisplay = _.partial(actionToCssDisplay,
            ['idle', 'save:ok', 'cancel']),

        actionToValidationErrorCssDisplay = _.partial(actionToCssDisplay,
            ['save:error']),

        displayValuesToFormFields = function() {
            $(displayFields).each(function(index, el) {
                var field = $(el).attr('data-field');
                var value = $(el).attr('data-value');
                var input;
                if (field) {
                    input = FH.getField($(editFields), field).find('input');
                    $(input).val(value);    
                }
            });
        },

        formFieldsToDisplayValues = function() {
            $(editFields).each(function(index, el){
                var field = $(el).attr('data-field');
                var input, value, display;
                if (field) {
                    input = FH.getField($(editFields), field).find('input');
                    value = input.val();
                    display = FH.getField($(displayFields), field);
                    $(display).attr('data-value', value);
                    $(display).html(value);
                }
            });
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
            _.each(errors, function (errorList, fieldName) {
                FH.getField($(validationFields), fieldName)
                    .html(errorList.join(','));
            });
        },

        isEditStart = function (action) {
            return action === 'edit:start';
        },

        responseStream = saveStream
            .map(FH.formToDictionary, $(form), $(editFields))
            .flatMap(update)
            .mapError(function (e) {
                return e.responseJSON;
            });

    responseStream.filter('.ok')
                  .onValue(formFieldsToDisplayValues);

    responseStream.filter('.error')
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
        responseStream.filter('.ok').map('save:ok')
    );

    actionStream.filter(isEditStart).onValue(displayValuesToFormFields);

    actionStream.map(actionToDisplayFieldCssDisplay)
                .toProperty('')
                .assign($(displayFields), "css", "display");

    actionStream.map(actionToEditFieldCssDisplay)
                .toProperty('none')
                .assign($(editFields), "css", "display");

    actionStream.map(actionToValidationErrorCssDisplay)
                .toProperty('none')
                .assign($(validationFields), "css", "display");
};
