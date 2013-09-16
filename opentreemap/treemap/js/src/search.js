"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require("underscore");

var config;

exports.buildElems = function (inputSelector) {
    return _.object(_.map($(inputSelector), function(el) {
        var $el = $(el),
            name = $el.attr('name'),
            type = $el.attr('data-search-type'),
            selector = inputSelector + '[name="' + name + '"][data-search-type="' + type + '"]';
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
        var pred = search[restoreTarget];
        var $domElem = $(k);
        if (pred) {
            pred = pred[v.pred];
        } else {
            pred = null;
        }

        $domElem.val(pred || '');
        $domElem.trigger('restore', pred);
    });
}

exports.applySearchToDom = applySearchToDom;

exports.reset = function (elems) {
    applySearchToDom(elems, {});
};

exports.buildSearch = function (elems) {
    return _.reduce(elems, function(preds, key_and_pred, id) {
        var val = $(id).val(),
            pred = {};

        if (val && val.length > 0) {
            // If a predicate field (such as tree.diameter)
            // is already specified, merge the resulting dicts
            // instead
            if (preds[key_and_pred.key]) {
                preds[key_and_pred.key][key_and_pred.pred] = val;
            } else {
                pred[key_and_pred.pred] = val;
                preds[key_and_pred.key] = pred;
            }
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
