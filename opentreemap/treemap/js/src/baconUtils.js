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

exports.truthyOrError = function (value) {
    return !!value ? value : Bacon.Error('The value ' + value + ' is not truthy');
};
