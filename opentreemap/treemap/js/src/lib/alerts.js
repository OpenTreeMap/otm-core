"use strict";

var _ = require('lodash'),
    toastr = require('toastr'),
    $ = require('jquery'),
    config = require('treemap/lib/config.js');

function makeCallback(method, config) {
    return function(errorJson) {
        var statusCode = errorJson.status ? errorJson.status.toString() : 'default',
            text = config.errorMessages[statusCode] || config.errorMessages.default;

        if (text.title && text.message) {
            method.call(toastr, text.message, text.title);
        } else if (text.message) {
            method.call(toastr, text.message);
        } else if (text.title) {
            method.call(toastr, '', text.title);
        }
    };
}

exports.errorCallback = makeCallback(toastr.error, config);
exports.makeWarningCallback = makeCallback(toastr.warning, config);
exports.makeInfoCallback = makeCallback(toastr.info, config);
