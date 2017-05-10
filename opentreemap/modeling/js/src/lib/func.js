"use strict";

var _ = require('lodash');

// This will return a function that will return a value. May save some
// typing if you just need a closure that returns a static value.
//
// Example:
//
// var foo = getter('bar');
// foo() => 'bar'
//
var getter = _.partial(_.partial, _.identity);

// Returns its arguments list as an array.
//
// This may be useful to use as an identity function when zipping or
// combining streams/properties in Bacon.
//
// Examples:
//
// Bacon.zipWith(argumentsToArray, stream1, stream2, ...)
//     .onValues(function(stream1, stream2, ...) {...});
//
// property.sampledBy(stream, argumentsToArray)
//     .onValues(function(property, stream) {...});
//
function argumentsToArray() {
    return Array.prototype.slice.apply(arguments);
}

// This is a function decorator that will apply an array as an arguments
// list to a given function. Kind of like array/tuple unpacking.
//
// Examples:
//
// var move = function(x, y) {...}
// move = expandArguments(move);
// move([0, 0]);
//
// property.sampledBy(stream, argumentsToArray)
//     .map(expandArguments(function(property, stream) {...}));
//
function expandArguments(fn, thisArg) {
    return function(arr) {
        return fn.apply(thisArg, arr);
    };
}

// This adds numbers together.
function sum(nums) {
    var argsLen = arguments.length;
    nums = argsLen == 1 ? nums : Array.prototype.slice.apply(arguments);

    // For compatibility with lodash functions.
    if (argsLen > 2 &&
            typeof arguments[argsLen - 1].length !== 'undefined') {
        nums.pop();
        nums.pop();
    }

    return _.reduce(
        nums,
        function(a, b) {
            return a + b;
        },
        0
    );
}

module.exports = {
    getter: getter,
    argumentsToArray: argumentsToArray,
    expandArguments: expandArguments,
    sum: sum
};
