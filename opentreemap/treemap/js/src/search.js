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
    var build = function build(typeAttr, el) {
        var $el = $(el),
            name = $el.attr('name') || $el.attr('data-search-identifier'),
            type = $el.attr(typeAttr),
            id = $el.attr('id'),
            buildSecondary = _.partial(build, 'data-search-secondary-type'),
            $subElems,
            children = {};

        if (type === "IN") {
            // Exclude further IN types to prevent infinite recursion
            $subElems = $('[data-search-secondary-type]:checkbox')
                .not('[data-search-secondary-type="IN"]');
            children = _.object(_.map($subElems, buildSecondary));
        }

        return[id, {
            'key': name,
            'pred': type,
            'children': children
        }];
    },
    buildPrimary = _.partial(build, 'data-search-type');

    return _.object(_.map($(inputSelector), buildPrimary));
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

function applySearchToInContainer($container, keyAndPred, search) {
    var searchPreds = search[keyAndPred.key],
        items = searchPreds ? searchPreds.IN : undefined,
        $checks = $container.find('[data-search-in]:checkbox');

    if (_.isArray(items)) {
        // If no elements are checked the list is [null] to be valid SQL
        items = _.reject(items, _.isNull);
        $checks.prop('checked', false);
        _.each(items, function(item) {
            $checks.filter('[data-search-in="' + item + '"]').prop('checked', true);
        });
    } else {
        // The lack of any filter for this IN clause means everything is checked
        $checks.prop('checked', true);
    }

    var preds = _(keyAndPred.children)
        .values()
        .uniq(JSON.stringify)
        .value();

    _.each(preds, function(keyAndPred) {
        var preds = search[keyAndPred.key],
            predValue = preds ? preds[keyAndPred.pred] : undefined,
            $predElems = $checks
                .filter('[name="' + keyAndPred.key + '"]')
                .filter('[data-search-secondary-type="' + keyAndPred.pred +'"]');

        if ( ! _.isUndefined(predValue)) {
            $predElems.prop('checked', false);
            $predElems
                .filter('[value="' + boolToText(predValue) + '"]')
                .prop('checked', true);
        }
    });
}

// Exported for testing
exports._applySearchToInContainer = applySearchToInContainer;

function applySearchToDom(elems, search) {
    _.each(elems, function(keyAndPred, id) {
        var $domElem = $(document.getElementById(id));
        var pred = search[keyAndPred.key];
        var value;

        if (pred && keyAndPred.pred === 'IN') {
            applySearchToInContainer($domElem, keyAndPred, search);
            return;
        }

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
    var buildQueryFromPred = function(identifier, pred) {
            var query = {};
            if ( ! _.isEmpty(pred)) {
                query[identifier] = pred;
            }
            return query;
        },

        buildQueryFromIn = function(id, keyAndPred) {
            var $elem = $(document.getElementById(id)),
                $checks = $elem.find('[data-search-in]:checkbox'),
                pred = {},
                inList;

            // If all elems are checked, don't add the IN predicate
            if ($checks.filter(':not(:checked)').length !== 0) {
                inList = _.map($checks.filter(':checked'), function(check) {
                    return $(check).attr('data-search-in');
                });
                inList = _.uniq(inList);
                // An empty IN clause is invalid SQL, so we need a dummy value
                pred[keyAndPred.pred] = inList.length !== 0 ? inList : [null];
            }
            return buildQueryFromPred(keyAndPred.key, pred);
        },

        buildQuery = function (key_and_pred, id) {
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

                if ($elem.is(':checkbox')) {
                    if ($elem.is(':checked')) {
                        pred[key_and_pred.pred] = textToBool(val);
                    }
                } else {
                    pred[key_and_pred.pred] = val;
                }
            }
            return buildQueryFromPred(key_and_pred.key, pred);
        };

    return _.reduce(elems, function (preds, key_and_pred, id) {
        var query = {},
            pred = {},
            childPreds,
            getKey = _.compose(_.first, Object.keys);

        if (key_and_pred.pred === 'IN') {
            query = buildQueryFromIn(id, key_and_pred);

            // Add the IN's children to the preds as well
            var allPreds = _(key_and_pred.children)
                .map(buildQuery)
                .reject(_.isEmpty)
                .value();

            _(allPreds)
                .groupBy(getKey)
                .each(function(childPreds, identifier) {
                    // groupBy leaves the elements unchanged, so we need to
                    // pluck out the inner objects, to get a list of {pred: value}
                    var identifierPreds = _.pluck(childPreds, identifier),

                        // If there are any contradictory predicates remove them
                        // (i.e. if there are two predicates of the same type with the same key)
                        //
                        // For example, if there are filters for {ISNULL: false} as
                        // well as {ISNULL: true}, we shouldn't add either to the
                        // query, as when searching for both plots with and without trees
                        unduplicatedKeys = _(identifierPreds)
                            .map(getKey)
                            .countBy()
                            .omit(function(number) {
                                return number > 1;
                            })
                            .keys()
                            .value(),

                        // identifierPred is a single object with all {pred: value}s
                        // merged, for all preds which only occurred once
                        identifierPred = _.pick(_.merge.apply(_, identifierPreds), unduplicatedKeys),

                        childQuery = buildQueryFromPred(identifier, identifierPred);

                    $.extend(true, preds, childQuery);
                });
        } else {
            query = buildQuery(key_and_pred, id);
        }

        // We do a deep extend so that if a predicate field
        // (such as tree.diameter) is already specified,
        // we merge the resulting dicts
        $.extend(true, preds, query);

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
