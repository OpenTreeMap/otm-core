"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),
    moment = require("moment"),
    isTypeaheadHiddenField = require('treemap/fieldHelpers'),
    FH = require('treemap/fieldHelpers');

var DATETIME_FORMAT = FH.DATETIME_FORMAT;

var isCombinator = function(pred) {
    return _.isArray(pred) && (pred[0] === "OR" || pred[0] === "AND");
};

var textToBool = function(text) {
    return _.isString(text) && text.toLowerCase() === "true";
};

var boolToText = function(bool) {
    return bool ? "true" : "false";
};

exports.buildElems = function (inputSelector) {
    return _.object(_.map($(inputSelector), function (typeAttr, el) {
        var $el = $(el),
            name = $el.attr('name'),
            type = $el.attr(typeAttr),
            id = $el.attr('id');

        return[id, {
            'key': name,
            'pred': type,
        }];
    }));
};

function executeSearch(config, search_query) {
    var search = $.ajax({
        url: config.instance.url + 'benefit/search',
        data: {'q': search_query && Object.keys(search_query).length > 0 ?
                JSON.stringify(search_query) :
                ''},
        type: 'GET',
        dataType: 'html'
    });

    return Bacon.fromPromise(search);
}

function updateSearchResults(newMarkup) {
    var $new = $(newMarkup),
        countsMarkup = $new.filter('#tree-and-planting-site-counts').html(),
        benefitsMarkup = $new.filter('#benefit-values').html();
    $('#tree-and-planting-site-counts').html(countsMarkup);
    $('#benefit-values').html(benefitsMarkup);
}

function applySearchToDom(elems, search) {
    _.each(elems, function(keyAndPred, id) {
        var $domElem = $(document.getElementById(id));
        var pred = search[keyAndPred.key];
        var value;

        if (isCombinator(pred)) {
            value = pred ? pred[1][keyAndPred.pred] : null;
        } else {
            value = pred ? pred[keyAndPred.pred] : null;
        }

        if ($domElem.is('[type="hidden"]')) {
            $domElem.trigger('restore', value);
        } else if ($domElem.is('[data-date-format]')) {
            FH.applyDateToDatepicker($domElem, value);
        } else if($domElem.is(':checkbox')) {
            $domElem.prop('checked', boolToText(value) === $domElem.val());
        } else if ($domElem.is('input')) {
            $domElem.val(value || '');
        }
    });
}

exports.applySearchToDom = applySearchToDom;

exports.reset = function (elems) {
    applySearchToDom(elems, {});
};

exports.buildSearch = function (elems) {
    return _.reduce(elems, function(preds, key_and_pred, id) {
        var $elem = $(document.getElementById(id)),
            val = $elem.val(),
            key = key_and_pred.key,
            pred = {},
            query = {};

        if ($elem.is(':checked') || ($elem.is(':not(:checkbox)') && val && val.length > 0)) {
            if ($elem.is('[data-date-format]')) {
                var date = moment($elem.datepicker('getDate'));
                if (key_and_pred.pred === "MIN") {
                    date = date.startOf("day");
                } else if (key_and_pred.pred === "MAX") {
                    date = date.endOf("day");
                }
                val = date.format(DATETIME_FORMAT);
            }

            if ($elem.is(":checkbox")) {
                if ($elem.is(":checked")) {
                    pred[key_and_pred.pred] = val;
                }
            } else {
                pred[key_and_pred.pred] = val;
            }

            // We do a deep extend so that if a predicate field
            // (such as tree.diameter) is already specified,
            // we merge the resulting dicts
            query[key] = pred;
            $.extend(true, preds, query);
        }

        return preds;
    }, {});
};

// Arguments
//
// searchStream: a Bacon.js EventStream. The value
//   of the item should be JSON generated from buildSearch
//
// applyFilter: Function to call when filter changes.
exports.init = function(searchStream, config, applyFilter) {
    searchStream.onValue(applyFilter);

    // Clear any previous search results
    searchStream.map('').onValue($('#search-results'), 'html');

    searchStream
        .flatMap(_.partial(executeSearch, config))
        .onValue(updateSearchResults);
};
