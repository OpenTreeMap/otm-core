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

var isEnterKey = exports.isEnterKey = keyCodeIs([13]);
exports.isEscKey = keyCodeIs([27]);

var isDefined = exports.isDefined = function (value) {
    return value !== undefined;
};

var isDefinedNonEmpty = exports.isDefinedNonEmpty = function (value) {
    return value !== undefined && value !== "";
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

exports.jsonRequest = function(verb, url) {
    return function(payload) {
        // url wasn't specififed
        if (arguments.length == 2) {
            payload = url;
        }

        var req = $.ajax({
            method: verb,
            url: url,
            contentType: 'application/json',
            data: JSON.stringify(payload)
        });

        return Bacon.fromPromise(req);
    };
};

exports.enterOrClickEventStream = function(options) {
    var inputs = $(options.inputs),
        button = $(options.button),
        enterKeyPressStream = inputs
            .asEventStream("keyup")
            .filter(isEnterKey),

        performSearchClickStream = button.asEventStream("click"),

        triggerEventStream = enterKeyPressStream.merge(
            performSearchClickStream);

    return triggerEventStream;
};
