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
                "pred": "ISNULL",
                "children": {}
            },
            "2": {
                "key": "tree.id",
                "pred": "ISNULL",
                "children": {}
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
                "pred": "ISNULL",
                "children": {}
            }
        },
        markup: '<div>' +
                '  <input id="1" data-search-identifier="tree.id" data-search-type="ISNULL" value="false" />' +
                '</div>'
    },
    "IN containers have no children if nothing is [data-search-secondary-type]": {
        obj: {
            "1": {
                "key": "mapfeature.feature_type",
                "pred": "IN",
                "children": {}
            }
        },
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" type="checkbox" name="tree.id" value="true" />' +
                '</div>'
    },
    "IN containers have children if they have [data-search-secondary-type]": {
        obj: {
            "1": {
                "key": "mapfeature.feature_type",
                "pred": "IN",
                "children": {
                    "2": {
                        "pred": "IS",
                        "key": "tree.id",
                        "children": {}
                    },
                    "3": {
                        "pred": "IS",
                        "key": "tree.id",
                        "children": {}
                    }
                }
            }
        },
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '</div>'
    }
};

var applySearchToInCases = {
    "If no filter is present, everything should be checked": {
        search: {},
        checked: {
            "2": true,
            "3": true,
            "4": true
        }
    },
    "If the filter is [null], everything should be unchecked": {
        search: {"mapfeature.feature_type":{"IN": [null]}},
        checked: {
            "2": false,
            "3": false,
            "4": false
        }
    },
    "If the filter is ['Plot'], only 'Plot' elements should be checked": {
        search: {"mapfeature.feature_type":{"IN": ["Plot"]}},
        checked: {
            "2": true,
            "3": true,
            "4": false
        }
    },
    "If the filter is ['Plot'], and a filter matches a secondary search type, only that 'Plot' element should be checked": {
        search: {"mapfeature.feature_type":{"IN": ["Plot"]}, "tree.id": {"IS": true}},
        checked: {
            "2": false,
            "3": true,
            "4": false
        }
    }
};

// TODO: test coverage for other predicates besides "IN"
var buildSearchCases = {
    "If all [data-search-in]s are checked, no filter should be generated": {
        search: {},
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" checked data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" checked data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '  <input id="4" checked data-search-in="Scheme" type="checkbox" />' +
                '</div>'
    },
    "If no [data-search-in]s are checked, the IN value should be [null]": {
        search: {"mapfeature.feature_type": {"IN": [null]}},
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '  <input id="4" data-search-in="Scheme" type="checkbox" />' +
                '</div>'
    },
    "If all Plot [data-search-in]s are checked, the IN value should be ['Plot'] and there should be no secondary search": {
        search: {"mapfeature.feature_type": {"IN": ["Plot"]}},
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" checked data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" checked data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '  <input id="4" data-search-in="Scheme" type="checkbox" />' +
                '</div>'
    },
    "If some Plot [data-search-in]s are checked, the IN value should be ['Plot'] and there should be a secondary search": {
        search: {"mapfeature.feature_type": {"IN": ["Plot", "Scheme"]}, "tree.id": {"IS": true}},
        markup: '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" checked data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '  <input id="4" checked data-search-in="Scheme" type="checkbox" />' +
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

            var elems = search.buildElems('[data-search-type]');
            assert.ok(elems);

            assert.deepEqual(elems, testCase.obj, 'The elems should match');

            $markup.remove();
        };
    }),
    "applySearchToInContainer": {
        'before': function() {
            this.keyAndPred = {
                "key": "mapfeature.feature_type",
                "pred": "IN",
                "children": {
                    "2": {
                        "pred": "IS",
                        "key": "tree.id",
                        "children": {}
                    },
                    "3": {
                        "pred": "IS",
                        "key": "tree.id",
                        "children": {}
                    }
                }
            };
            this.markup = '<div id="1" data-search-type="IN" data-search-identifier="mapfeature.feature_type">' +
                '  <input id="2" data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="false" />' +
                '  <input id="3" data-search-in="Plot" data-search-secondary-type="IS" type="checkbox" name="tree.id" value="true" />' +
                '  <input id="4" data-search-in="Scheme" type="checkbox" />' +
                '</div>';
        }
    },
    "buildSearch": {
        'before': function() {
            this.elems = {
                "1": {
                    "key": "mapfeature.feature_type",
                    "pred": "IN",
                    "children": {
                        "2": {
                            "pred": "IS",
                            "key": "tree.id",
                            "children": {}
                        },
                        "3": {
                            "pred": "IS",
                            "key": "tree.id",
                            "children": {}
                        }
                    }
                }
            };
        }
    }
};

_.extend(module.exports.applySearchToInContainer, _.mapValues(applySearchToInCases, function(testCase) {
    return function() {
        var $markup = $(this.markup);
        $('#search').append($markup);

        search._applySearchToInContainer($markup, this.keyAndPred, testCase.search);

        _.each(testCase.checked, function(value, id) {
            assert.equal(value, document.getElementById(id).checked, 'Checkbox ' + id + ' should be ' + value);
        });

        $markup.remove();
    };
}));

_.extend(module.exports.buildSearch, _.mapValues(buildSearchCases, function(testCase) {
    return function() {
        var $markup = $(testCase.markup);
        $('#search').append($markup);

        var filterObj = search.buildSearch(this.elems);
        assert.ok(filterObj);

        assert.deepEqual(testCase.search, filterObj, 'The filter objects should match');

        $markup.remove();
    };
}));
