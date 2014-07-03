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
    },
    "Handles udfc field syntax correctly": {
        obj: {
            "udfc-search-action": {
                "key": "udf:plot:18.Action",
                "pred": "IS"
            }
        },
        markup:
        '<select id="udfc-search-action" data-search-type="IS" name="udf:plot:18.Action">' +
            '<option data-class="udfc-placeholder" selected="" style="display: inline;">' +
            '<option data-model="plot" style="">Enlarging the Planting Area</option>' +
            '<option data-model="plot" style="">Adding a Guard</option>' +
            '<option data-model="plot" style="">Removing a Guard</option>' +
            '<option data-model="plot" style="">Herbaceous Planting</option>' +
            '</select>'
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
    "buildElems": _.mapValues(buildElemsCases, function(TestCase) {
        return function() {
            var $markup = $(testCase.markup);
            $('#search').append($markup);

            var elems = search._buildElems();
            assert.ok(elems);

            assert.deepEqual(elems, testCase.obj, 'The elems should match');

            $markup.remove();
        };
    })
};
