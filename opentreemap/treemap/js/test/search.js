"use strict";

var assert = require('chai').assert,
    search = require('treemap/search'),
    $ = require('jquery'),
    _ = require('lodash');

var buildElemsCases = {
    "Each element has a matching key/pred pair, even if they share the same identifier and predicate": {
        obj: {
            "1": {
                "key": "tree.id",
                "pred": "ISNULL"
            },
            "2": {
                "key": "tree.id",
                "pred": "ISNULL"
            }
        },
        markup: '<div>' +
                '  <input id="1" type="checkbox" name="tree.id" data-search-type="ISNULL" value="false" />' +
                '  <input id="2" type="checkbox" name="tree.id" data-search-type="ISNULL" value="true" />' +
                '</div>'
    },
    "data-search-identifier is used if name is not set": {
        obj: {
            "1": {
                "key": "tree.id",
                "pred": "ISNULL"
            }
        },
        markup: '<div>' +
                '  <input type="checkbox" id="1" data-search-identifier="tree.id" data-search-type="ISNULL" value="false" />' +
                '</div>'
    }
};

module.exports = {};

module.exports = {
    "before": function() {
        $('body').append('<div id="search" />');
    },
    "afterEach": function() {
        $('#search').empty();
    },
    "builldElems": _.mapValues(buildElemsCases, function(testCase) {
        return function() {
            var $markup = $(testCase.markup);
            $('#search').append($markup);

            var elems = search._buildElems('[data-search-type]');
            assert.ok(elems);

            assert.deepEqual(elems, testCase.obj, 'The elems should match');

            $markup.remove();
        };
    })
};
