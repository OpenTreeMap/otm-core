"use strict";

var $ = require('jquery'),
    _ = require('lodash'),

    makeNameAttribute = _.template('udf:<%= modelName %>:<%= udfFieldDefId %>.<%= fieldKey %>'),

    MODEL_SELECT_SELECTOR = '#stewardship-search-model',
    ACTION_SELECT_SELECTOR = '#stewardship-search-action',
    DATE_MIN_SELECTOR = '#stewardship-search-date-from',
    DATE_MAX_SELECTOR = '#stewardship-search-date-to',

    MODEL_TO_UI_VALUE = {'udf:tree': 'trees', 'udf:mapFeature': 'plots' };

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.applyFilterObjectToDom = function (search) {
    var parsed = _.filter(_.map(search.filter, function (v, k) {
            // parse each field name and update the filterObject to also
            // contain the parse results
            var fieldNameData = parseUdfCollectionFieldName(k);
            if (fieldNameData) {
                return _.extend({}, v, fieldNameData);
            } else {
                return null;
            }
        })),
        modelName = _.uniq(_.pluck(parsed, 'modelName'))[0],
        action,
        date;

    // there's no data if there's no modelName
    // don't attempt to populate if invalid data provided
    if (!_.isString(modelName) ||
        !_.contains(_.keys(MODEL_TO_UI_VALUE), modelName)) {
        return;
    }

    // set the model name in the model selector and initialize fields
    $(MODEL_SELECT_SELECTOR).val(MODEL_TO_UI_VALUE[modelName]);
    initializeUiBasedOnModelType();

    // set the action select box to the action in the filter object
    action = _.where(parsed, {hStoreMember: 'Action'})[0];
    if (_.isString(action)) {
        $(ACTION_SELECT_SELECTOR).val(action.IS);
    }

    // set the upper and lower date bounds
    date = _.where(parsed, {hStoreMember: 'Date'})[0];
    if (!_.isUndefined(date)) {
        if (_.isString(date.MIN)) {
            $(DATE_MIN_SELECTOR).val(date.MIN);
        }
        if (_.isString(date.MAX)) {
            $(DATE_MAX_SELECTOR).val(date.MAX);
        }
    }
};

function initializeUiBasedOnModelType() {
    // after changing modelSelectBox, attributes on the remaining
    // stewardship dom elements need to be modified.

    var $modelSelectBox = $(MODEL_SELECT_SELECTOR),
        $actionSelectBox = $(ACTION_SELECT_SELECTOR),
        $actionOptions = $actionSelectBox.find('option'),
        modelName = $modelSelectBox.find('option:selected').attr('data-model'),
        udfFieldDefId = $modelSelectBox.find('option:selected').attr('data-udfd-id');

    // reset the action select to empty and only show the relevant options
    $actionSelectBox.val('');
    $actionOptions.not('[data-model="' + modelName + '"]').hide();
    $actionOptions.filter('[data-model="' + modelName + '"]').show();
    $actionOptions.filter('[data-class="stewardship-placeholder"]').show();

    // set the updated udfFieldDefId on the action select and the date inputs
    $actionSelectBox.attr('name',
                           makeNameAttribute({ modelName: modelName,
                                               udfFieldDefId: udfFieldDefId,
                                               fieldKey: 'Action' }));
    $('[id^=stewardship-search-date-]').attr('name',
                                             makeNameAttribute({ modelName: modelName,
                                                                 udfFieldDefId: udfFieldDefId,
                                                                 fieldKey: 'Date' }));
}

function clearUi() {
    $(MODEL_SELECT_SELECTOR).val('');
    initializeUiBasedOnModelType();
}

exports.init = function (config) {
    // the model selector is managed by this module, not by the advanced search.
    // all it does is set the pk/string on each of the "real" advanced search fields.
    config.resetStream.onValue(clearUi);
    $(MODEL_SELECT_SELECTOR).change(initializeUiBasedOnModelType);
};

// Copied from OTM2-Tiler, documentation removed.
// TODO: factor this out into a common node module
function parseUdfCollectionFieldName (fieldName) {
    var tokens = fieldName.split(':'),
        fieldDefIdAndHStoreMember;

    if (tokens.length !== 3) {
        return null;
    }

    fieldDefIdAndHStoreMember = tokens[2].split('.');

    return {
        modelName: 'udf:' + tokens[1],
        fieldDefId: fieldDefIdAndHStoreMember[0],
        hStoreMember: fieldDefIdAndHStoreMember[1]
    };
}
