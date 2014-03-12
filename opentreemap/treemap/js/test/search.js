"use strict";

var assert = require('chai').assert,
    search = require('treemap/search'),
    $ = require('jquery'),
    _ = require('lodash');

var makeData = function () {
    var elems = {
        "[data-search-type][name=\"tree.diameter\"][data-search-type=\"MIN\"]" : {
            "key": "tree.diameter",
            "pred": "MIN"
        },
        "[data-search-type][name=\"tree.diameter\"][data-search-type=\"MAX\"]": {
            "key": "tree.diameter",
            "pred":"MAX"
        },
        "[data-search-type][name=\"tree.id\"][data-search-type=\"ISNULL\"][value=\"false\"]": {
            "key":"tree.id",
            "pred":"ISNULL"
        },
        "[data-search-type][name=\"tree.id\"][data-search-type=\"ISNULL\"][value=\"true\"]": {
            "key":"tree.id",
            "pred":"ISNULL"
        }
    };
    return {
        markup: "" +
            '<div id="search">' +
            '  <input type="checkbox" name="tree.id" data-search-type="ISNULL" value="false" />' +
            '  <input type="checkbox" name="tree.id" data-search-type="ISNULL" value="true" />' +
            '  <input name="tree.diameter" data-search-type="MIN" />' +
            '  <input name="tree.diameter" data-search-type="MAX" />' +
            '</div>',
        obj: elems
    };
};

module.exports = {
    'before': function () {
        this.data = makeData();
        $('body').append(this.data.markup);
    },
    'after': function () {
        $('#search').remove();
    },
    'buildElems should map 1-1 for every search input' : function () {
        var elems = search.buildElems('[data-search-type]');
        assert.ok(elems);

        _.each(elems, function(value, key) {
            assert.equal($(key).length, 1, 'The selector should only match 1 element');
        });

        assert.deepEqual(elems, this.data.obj, 'The elems object is as expected');
    }
};
