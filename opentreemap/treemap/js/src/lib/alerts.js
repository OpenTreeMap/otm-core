"use strict";

var _ = require('lodash'),
    toastr = require('toastr'),
    $ = require('jquery');

function makeCallback(method, config, options) {
    return function(errorJson) {
        var statusCode = errorJson.status ? errorJson.status.toString() : 'default',
            text = config.errorMessages[statusCode] || config.errorMessages.default;

        options = options || {};
        if (text.title && text.message) {
            method.call(toastr, text.message, text.title, options);
        } else if (text.message) {
            method.call(toastr, text.message, options);
        } else if (text.title) {
            method.call(toastr, '', text.title, options);
        }
    };
}

exports.makeErrorCallback = _.partial(makeCallback, toastr.error);
exports.makeWarningCallback = _.partial(makeCallback, toastr.warning);
exports.makeInfoCallback = _.partial(makeCallback, toastr.info);
