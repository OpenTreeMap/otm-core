"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    R = require('ramda'),
    _ = require('lodash'),
    format = require('util').format,
    M = require('treemap/lib/BaconModels.js'),
    moment = require('moment'),
    getOptionAttr = M.getOptionAttr,
    getVal = M.getVal,
    DATETIME_FORMAT = require('treemap/lib/fieldHelpers.js').DATETIME_FORMAT;

// Placed onto the jquery object
require('bootstrap-datepicker');

var nameTemplate = _.template('udf:<%= modelName %>:<%= udfFieldDefId %>.<%= fieldKey %>'),

    widgets = {
        modelName: {
            selector: '#udfc-search-model',
            reset: _.partial(resetSelectWidget, 'modelName', 'data-model'),
            stateModifiers: { 
                modelName: getOptionAttr('data-model'),
                action: null 
            }
        },
        type: {
            selector: '#udfc-search-type',
            reset: _.partial(resetType, 'type', 'data-type'),
            stateModifiers: {
                type: getOptionAttr('data-type'),
                udfFieldDefIds: getOptionAttr('data-udfd-ids'),
                actionFieldKey: getOptionAttr('data-action-field-key'),
                dateFieldKey: getOptionAttr('data-date-field-key'),
                action: null
            }
        },
        action: {
            selector: '#udfc-search-action',
            reset: resetAction,
            stateModifiers: {action: getVal}
        },
        dateMin: {
            selector: '#udfc-search-date-from',
            reset: _.partial(resetDateBox, 'dateMin'),
            stateModifiers: {dateMin: getVal}
        },
        dateMax: {
            selector: '#udfc-search-date-to', 
            reset: _.partial(resetDateBox, 'dateMax'),
            stateModifiers: {dateMax: getVal }
        },
        extraClauses: {
            selector: '#udfc-extra-clauses',
            reset: resetExtraClauses
        }
    },
    emptyState = _(widgets)
        .map('stateModifiers')
        .map(_.keys)
        .flatten()
        .uniq()
        .map(function (key) { return [key, null]; })
        .fromPairs()
        .value();

function makeNameAttribute (state, fieldKey) {
    var modelName = state.modelName,
        requiredFields = [modelName,
                          state.actionFieldKey,
                          state.dateFieldKey,
                          state.udfFieldDefIds],
        udfFieldDefId;

    if (_.some(requiredFields, R.either(_.isUndefined, _.isNull))) {
        return '';
    }

    udfFieldDefId = JSON.parse(state.udfFieldDefIds)[modelName];

    if (_.isUndefined(udfFieldDefId)) {
        return '';
    }

    return nameTemplate({modelName: modelName,
                      udfFieldDefId: udfFieldDefId,
                      fieldKey: fieldKey});
}


function resetSelectWidget(widgetName, optionKey, state) {
    var stateVal = state[widgetName],
        $option,
        val;

    if (!_.isNull(stateVal)) {
        $option = $(widgets[widgetName].selector)
            .find('option')
            .filter('[' + optionKey + '="' + stateVal + '"]');
        val = $option.val();
    } else {
        val = '';
    }
    $(widgets[widgetName].selector).val(val);
}

function resetType(widgetName, optionKey, state) {
    resetSelectWidget(widgetName, optionKey, state);
    var $el = $(widgets.type.selector),
        shouldEnable = !_.isNull(state.modelName);
    enableInput($el, shouldEnable);
}

function enableInput($el, shouldEnable) {
    $el.prop('disabled', shouldEnable ? false : 'disabled');
}

function resetAction(state) {
    var $el = $(widgets.action.selector),
        $currentOptions = $el.find('option').not('[data-class="udfc-placeholder"]'),
        $allOptions = $el.data('options'),
        shouldEnable = !_.isNull(state.modelName) && !_.isNull(state.type),
        modelSelector,
        typeSelector;

    // You can't hide <option> tags, so we need to stash them and add/remove
    // them as needed
    if (_.isUndefined($allOptions)) {
        $allOptions = $currentOptions.detach();
        $el.data('options', $allOptions);
    }

    $currentOptions.remove();
    if (shouldEnable) {
        modelSelector = format('[data-model="%s"]', state.modelName);
        typeSelector = format('[data-type="%s"]', state.type);

        // Add the relevant options to the select
        $allOptions
            .filter(modelSelector)
            .filter(typeSelector)
            .appendTo($el);
    }
    enableInput($el, shouldEnable);

    $el = $(widgets.action.selector);
    if (!_.isNull(state.action)) {
        $el.val(state.action);
    } else {
        $el.val('');
    }
    $el.attr('name', makeNameAttribute(state, state.actionFieldKey));
}

function resetDateBox(widgetName, state) {
    var name = makeNameAttribute(state, state.dateFieldKey),
        $widget = $(widgets[widgetName].selector),
        // Passing `true` as the third argument when creating a moment enables
        // strict mode, which we need for the `isValid` check below to work
        // properly.
        longDate = moment(state[widgetName], DATETIME_FORMAT, true),
        shortDate = moment(state[widgetName], 'MM/DD/YYYY', true),
        shouldEnable = !_.isNull(state.modelName) && !_.isNull(state.type),
        val;

    if (shouldEnable) {
        if (!_.isNull(longDate) && longDate.isValid()) {
            val = longDate.format('MM/DD/YYYY');
        } else if (!_.isNull(shortDate) && shortDate.isValid()) {
            val = shortDate.format('MM/DD/YYYY');
        } else {
            val = '';
        }
    }
    enableInput($widget, shouldEnable);

    $widget.attr('name', name);
    $widget.val(val);
}

function resetExtraClauses(state) {
    var $els = $(widgets.extraClauses.selector).find('input'),
        name;

    $els.attr('name', '');

    if (_.isNull(state.type)) { return; }

    var $matches = $els.filter('[data-type="' + state.type  + '"]');
    _.each($matches, function (match) {
        var $match = $(match),
            field = $match.attr('data-field'),
            name = makeNameAttribute(state, field);
        $match.attr('name', name);
        // this is a concession. Why won't value stick?
        $match.val($match.attr('value'));
    });
}

function applyFilterObjectToDom(bus, filterObject) {
    var state = _.extend({}, emptyState),
        parsed = _.filter(_.map(filterObject.filter, function (v, k) {
            // parse each field name and update the filterObject to also
            // contain the parse results
            var fieldNameData = parseUdfCollectionFieldName(k);
            if (fieldNameData) {
                return _.extend({}, v, fieldNameData);
            } else {
                return null;
            }
        })),
        modelName = _.uniq(_.map(parsed, 'modelName'))[0],
        udfFieldDefId = _.uniq(_.map(parsed, 'fieldDefId'))[0],
        eligibleModelNames = _.map(
            $(widgets.modelName.selector)
                .find('option')
                .not('[data-class="udfc-placeholder"]'),
            function (option) {
                return $(option).attr('data-model');
            }),
        cleanModelName,
        action,
        date;

    // there's no data if there's no modelName / udfFieldDefId
    if (!_.isString(modelName) || !_.isString(udfFieldDefId)) { return; }

    // don't attempt to populate if invalid data provided
    cleanModelName = modelName.substring(4);
    if (!_.includes(eligibleModelNames, cleanModelName)) { return; }
    state.modelName = cleanModelName;

    var $typeEl = $(widgets.type.selector)
            .find('option[data-udfd-ids]')
            .filter(function (__, el) {
                var id = JSON.parse($(el).attr('data-udfd-ids'))[cleanModelName];
                return id == udfFieldDefId;
            });

    state.udfFieldDefIds = $typeEl.attr('data-udfd-ids');
    state.dateFieldKey = $typeEl.attr('data-date-field-key');
    state.actionFieldKey = $typeEl.attr('data-action-field-key');
    state.type = $typeEl.attr('data-type');

    // set the model name in the model selector and initialize fields
    state.action = _.filter(parsed, {hStoreMember: state.actionFieldKey})[0].IS;

    date = _.filter(parsed, {hStoreMember: state.dateFieldKey})[0];
    if (!_.isUndefined(date)) {
        state.dateMin = _.isString(date.MIN) ? date.MIN : null;
        state.dateMax = _.isString(date.MAX) ? date.MAX : null;
    }

    bus.push(state);
}

// exported for testing
exports._makeNameAttribute = makeNameAttribute;
exports._widgets = widgets;

exports.init = function (resetStream) {
    var resetStateStream = (resetStream || Bacon.never()).map(emptyState),
        externalChangeBus = new Bacon.Bus();

    var globalState = M.init({
            externalStreams: [externalChangeBus, resetStateStream],
            widgets: widgets,
            emptyState: emptyState
        });

    return {
        applyFilterObjectToDom: _.partial(applyFilterObjectToDom,
                                          externalChangeBus),
        _externalChangeBus: externalChangeBus        // for unit testing
    };
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
