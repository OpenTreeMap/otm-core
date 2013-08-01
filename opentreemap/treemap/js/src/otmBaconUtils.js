"use strict";

var Bacon = require('baconjs'),
    $ = require('jquery');

$.extend($.fn, Bacon.$);

/* BEGIN BACON HELPERS */

function keyCodeIs (keyCodes) {
    return function(event) {
        for (var i = 0; i < keyCodes.length; i++) {
            if (event.which === keyCodes[i]) {
                return true;
            }
        }
        return false;
    };
};
exports.keyCodeIs = keyCodeIs;

exports.isEnterKey = keyCodeIs([13]);

exports.truthyOrError = function (value) {
    return !!value ? value : Bacon.Error('The value ' + value + ' is not truthy');
};

/* END BACON HELPERS */
