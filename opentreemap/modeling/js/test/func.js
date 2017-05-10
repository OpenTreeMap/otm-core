"use strict";

var assert = require('chai').assert,
    _ = require('lodash'),
    F = require('modeling/lib/func.js');

var funcTests = {
    'getter': function() {
        assert.equal(F.getter('foo')(), 'foo');
    },
    'argumentsToArray': function() {
        var actual = F.argumentsToArray('foo', 'bar');
        assert.equal(actual[0], 'foo');
        assert.equal(actual[1], 'bar');

    },
    'expandArguments': function() {
        var foo = function(a, b) {
            return '[' + a + ', ' + b + ']';
        };
        foo = F.expandArguments(foo);
        assert.equal(foo([1, 2]), '[1, 2]');
    },
    'sum': function() {
        assert.equal(
            F.sum([1, 2, 3, 4, 5]),
            15,
            'Sum should accept array as first argument'
        );
        assert.equal(
            F.sum(1, 2, 3, 4, 5),
            15,
            'Sum should accept arguments list'
        );
        assert.deepEqual(
            _.map([1, 2, 3], _.partial(F.sum, 1)),
            [2, 3, 4],
            'Last 2 arguments of lodash callbacks should be ignored'
        );
        assert.equal(
            _.reduce([1, 2, 3], F.sum),
            6,
            'Redundant but should still work'
        );
    }
};

module.exports = {
    'modeling/func': funcTests
};
