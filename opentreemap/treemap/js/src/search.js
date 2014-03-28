"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),
    moment = require("moment"),
    isTypeaheadHiddenField = require('treemap/fieldHelpers'),
    FH = require('treemap/fieldHelpers');

var DATETIME_FORMAT = FH.DATETIME_FORMAT;
var TREE_MODELS = ['Tree', 'EmptyPlot'];

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
    return _.object(_.map($(inputSelector), function (el) {
        var $el = $(el),
            name = $el.attr('name') || $el.attr('data-search-identifier'),
            type = $el.attr('data-search-type'),
            id = $el.attr('id');

        return[id, {
            'key': name,
            'pred': type,
        }];
    }));
};

function executeSearch(config, filters) {
    var searchQuery = filters.filter,
        displayQuery = filters.display;

    // An empty filter object is serialized as an empty string
    searchQuery = searchQuery && Object.keys(searchQuery).length > 0 ?
            JSON.stringify(searchQuery) :
            '';
    displayQuery = displayQuery && displayQuery.length > 0 ?
            JSON.stringify(displayQuery) :
            '';
    var search = $.ajax({
        url: config.instance.url + 'benefit/search',
        data: {'q': searchQuery, 'show': displayQuery},
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

function applyFilterObjectToDom(elems, search) {
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

function applyDisplayListToDom(displayList) {
    var checkDisplayFilter = function(filter) {
        $('[data-search-display="' + filter + '"]').prop('checked', true);
    };
    if (displayList) {
        $('[data-search-display]').prop('checked', false);
        _.each(displayList, checkDisplayFilter);
        if (_.contains(displayList, 'Plot')) {
            _.each(TREE_MODELS, checkDisplayFilter);
        }
    } else {
        $('[data-search-display]').prop('checked', true);
    }
}

function applySearchToDom(elems, search) {
    applyFilterObjectToDom(elems, search.filter || {});
    applyDisplayListToDom(search.display);
}

exports.applySearchToDom = applySearchToDom;

exports.reset = function (elems) {
    applySearchToDom(elems, {});
};

exports.buildSearch = function (elems) {
    return {
        'filter': buildFilterObject(elems),
        'display': buildDisplayList()
    };
};

function buildFilterObject (elems) {
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
                    pred[key_and_pred.pred] = textToBool(val);
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
}

function buildDisplayList() {
    var filters =  _($('[data-search-display]'))
            .filter('checked')
            .map(function(el) {
                return $(el).attr('data-search-display');
            })
            .value(),
        filtersWithoutTreeModels = _.difference(filters, TREE_MODELS);

    if ((filters.length - filtersWithoutTreeModels.length) === TREE_MODELS.length) {
        return filtersWithoutTreeModels.concat('Plot');
    }
    return filters;
}

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
