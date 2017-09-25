"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),
    reverse = require('reverse'),
    moment = require("moment"),
    isTypeaheadHiddenField = require('treemap/lib/fieldHelpers.js'),
    FH = require('treemap/lib/fieldHelpers.js'),
    config = require('treemap/lib/config.js'),
    querystring = require('querystring'),
    locationSearchUI = require('treemap/mapPage/locationSearchUI.js');

var DATETIME_FORMAT = FH.DATETIME_FORMAT;
var TREE_MODELS = ['Tree', 'EmptyPlot'];
var SEARCH_FIELD_SELECTOR = '[data-search-type]';

var isCombinator = function(pred) {
    return _.isArray(pred) && (pred[0] === "OR" || pred[0] === "AND");
};

var textToBool = function(text) {
    return _.isString(text) && text.toLowerCase() === "true";
};

var boolToText = function(bool) {
    return bool ? "true" : "false";
};

var filterObjectIsEmpty = exports.filterObjectIsEmpty = function(filterObj) {
    return filterObj ? _.keys(filterObj).length === 0 : true;
};

var displayListIsEmpty = exports.displayListIsEmpty = function(displayList) {
    return _.isUndefined(displayList) || _.isNull(displayList);
};

var isEmpty = exports.isEmpty = function(obj) {
    return filterObjectIsEmpty(obj.filter) && displayListIsEmpty(obj.display);
};

var makeQueryStringFromFilters = exports.makeQueryStringFromFilters = function(filters) {
    var query = {};
    if ( ! filterObjectIsEmpty(filters.filter)) {
        query[config.urls.filterQueryArgumentName] = JSON.stringify(filters.filter);
    }
    if ( ! displayListIsEmpty(filters.display)) {
        query[config.urls.displayQueryArgumentName] = JSON.stringify(filters.display);
    }
    return querystring.stringify(query);
};

// ``buildElems`` produces a data structure to be used by a number of
// functions in this module. The structure is an object, where the
// keys are equal to dom element id attributes for search fields. The
// values are objects that map to search/filter parameters. This
// pairing preserves a two-way relationship between dom elements and
// search parameters, so that they can be used to put a search on the
// dom or a dom into the search.
function buildElems() {
    return _.fromPairs(_.map($(SEARCH_FIELD_SELECTOR), function (el) {
        var $el = $(el),
            name = $el.attr('name') || $el.attr('data-search-identifier'),
            type = $el.attr('data-search-type'),
            id = $el.attr('id');

        return[id, {
            'key': name,
            'pred': type
        }];
    }));
}

// export as underscore method so it can
// be conveniently used in unit tests
exports._buildElems = buildElems;

function executeSearch(filters) {
    var query = makeQueryStringFromFilters(filters);

    var search = $.ajax({
        url: reverse.benefit_search(config.instance.url_name),
        data: query,
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

function applyFilterObjectToDom(search) {
    var elems = buildElems();

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
        } else if ($domElem.is(':checkbox')) {
            $domElem.prop('checked', boolToText(value) === $domElem.val());
        } else if ($domElem.is('input,select')) {
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
        if (_.includes(displayList, 'Plot')) {
            _.each(TREE_MODELS, checkDisplayFilter);
        }
    } else {
        $('[data-search-display]').prop('checked', true);
    }
}

function applyAddressToBoundaryTypeahead(filter, address) {
    if (!hasBoundaryFilter(filter) && address) {
        $('#boundary-typeahead').typeahead('val', address);
        locationSearchUI.showAppropriateWellButton();
    }
}

function applySearchToDom(search) {
    applyFilterObjectToDom(search.filter || {});
    applyDisplayListToDom(search.display);
    applyAddressToBoundaryTypeahead(search.filter, search.address);
}

exports.applySearchToDom = applySearchToDom;

exports.reset = _.partialRight(applySearchToDom, {});

exports.buildSearch = function () {
    var filter = buildFilterObject();
    return {
        'filter': filter,
        'display': buildDisplayList(),
        'address': getAddressIfSet(filter)
    };
};

function buildFilterObject () {
    var elems = buildElems();

    return _.reduce(elems, function(preds, key_and_pred, id) {
        var $elem = $(document.getElementById(id)),
            val = $elem.val(),
            key = key_and_pred.key,
            pred = {},
            query = {};

        if ($elem.is(':checked') || ($elem.is(':not(:checkbox)') && val && val.length > 0)) {
            if ($elem.is('[data-date-format]')) {
                var date = moment($elem.datepicker('getDate') || $elem.val());
                if (key_and_pred.pred === "MIN") {
                    date = date.startOf("day");
                } else if (key_and_pred.pred === "MAX") {
                    date = date.endOf("day");
                }
                val = date.format(DATETIME_FORMAT);
            } else if ($elem.is(":checkbox")) {
                if ($elem.is(":checked")) {
                    val = textToBool(val);
                }
            } else if (_.includes(['MIN', 'MAX'], key_and_pred.pred)) {
                // range searches (min and max) are the only type in which
                // comparison as text will yield undesirable results for
                // numbers. Casting to float is satisfactory because it
                // will make numeric comparison more flexible, and range
                // searches on text don't make sense.
                val = parseFloat(val);
            } else if ($elem.is('[data-remote]')) {
                val = parseInt(val, 10);
            } else {
                val = val;
            }
            pred[key_and_pred.pred] = val;

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
    var $elems = $('[data-search-display]'),
        $checkedElems = _.filter($elems, 'checked'),
        filters, filtersWithoutTreeModels;

    if ($elems.length === $checkedElems.length) {
        return null;
    }

    filters = _.map($checkedElems, function(el) {
        return $(el).attr('data-search-display');
    });
    filtersWithoutTreeModels = _.difference(filters, TREE_MODELS);

    if ((filters.length - filtersWithoutTreeModels.length) === TREE_MODELS.length) {
        return filtersWithoutTreeModels.concat('Plot');
    }
    return filters;
}

function getAddressIfSet(filter) {
    // If the filter contains a boundary query, the text in the location search
    // box is not an address
    if (hasBoundaryFilter(filter)) {
        return undefined;
    }
    return $('#boundary-typeahead').val() || undefined;
}

function hasBoundaryFilter(filter) {
    return filter && filter['mapFeature.geom'] && filter['mapFeature.geom'].IN_BOUNDARY;
}

// Arguments
//
// searchStream: a Bacon.js EventStream. The value
//   of the item should be JSON generated from buildSearch
//
// applyFilter: Function to call when filter changes.
exports.init = function(searchStream, applyFilter) {
    searchStream.onValue(applyFilter);

    var completedSearch = searchStream
        .flatMap(executeSearch);

    completedSearch.onValue(updateSearchResults);

    return completedSearch;
};
