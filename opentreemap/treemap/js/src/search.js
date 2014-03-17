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

exports.buildElems = function (inputSelector) {
    return _.object(_.map($(inputSelector), function(el) {
        var $el = $(el),
            name = $el.attr('name'),
            type = $el.attr('data-search-type'),
            selector = inputSelector + '[name="' + name + '"][data-search-type="' + type + '"]';
        if ($el.is(':checkbox')) {
            // Checkboxes have a set value attribute, which is part of their
            // selector
            selector += '[value="' + $el.val() + '"]';
        }
        return[selector, {
            'key': name,
            'pred': type
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
    _.each(elems, function(v, k) {
        var restoreTarget = v['restore-to'] || v.key;
        var $domElem = $(k);
        var pred = search[restoreTarget];
        var value = pred ? pred[v.pred] : null;

        if (isCombinator(pred)) {
            value = pred ? pred[1][v.pred] : null;
        } else {
            value = pred ? pred[v.pred] : null;
        }

        if ($domElem.is('[type="hidden"]')) {
            $domElem.trigger('restore', value);
        } else if ($domElem.is('[data-date-format]')) {
            FH.applyDateToDatepicker($domElem, value);
        } else if($domElem.is(':checkbox')) {
            $domElem.prop('checked', value === $domElem.val());
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
    return _.reduce(elems, function(preds, key_and_pred, selector) {
        var $elem = $(selector),
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
