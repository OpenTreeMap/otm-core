"use strict";

var Bacon = require('baconjs'),
    $ = require('jquery');

// Bacon.js is an npm module, but only extends jQuery if it's a global object
// So we need to add extend jQuery with Bacon methods manually
$.extend($.fn, Bacon.$);

function keyCodeIs (keyCodes) {
    return function(event) {
        for (var i = 0; i < keyCodes.length; i++) {
            if (event.which === keyCodes[i]) {
                return true;
            }
        }
        return false;
    };
}
exports.keyCodeIs = keyCodeIs;

exports.isEnterKey = keyCodeIs([13]);

var isDefined = exports.isDefined = function (value) {
    return value !== undefined;
};

var isUndefined = exports.isUndefined = function (value) {
    return value === undefined;
};

exports.fetchFromIdStream = function (idStream, fetchFn, undefinedMapping, errorMapping) {
    return Bacon.mergeAll(
        idStream
            .filter(isDefined)
            .flatMap(fetchFn)
            .mapError(errorMapping),
        idStream
            .filter(isUndefined)
            .map(undefinedMapping));
};