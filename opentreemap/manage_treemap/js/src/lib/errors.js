"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    mustache = require('mustache');

var fieldErrorsTemplate = mustache.compile(
    $('#field-error-template').html());

var globalErrorsTemplate = mustache.compile(
    $('#global-errors-template').html());

module.exports.convertErrorObjectIntoHtml = function (rawErrorObject) {
    var errorObject = JSON.parse(rawErrorObject.responseText),
        cleanFieldErrors = _.map(errorObject.fieldErrors, function(msgs, field) {
            return {field: stripUdfPrefix(field), message: msgs};
        }),
        cleanErrorObject = {
            errors: cleanFieldErrors,
            globalErrors: errorObject.globalErrors
        },
        globalErrorHtml = globalErrorsTemplate(cleanErrorObject),
        fieldErrorHtml = fieldErrorsTemplate(cleanErrorObject);

    return globalErrorHtml + fieldErrorHtml;
};

function stripUdfPrefix(field) {
    return field.indexOf('udf.') === 0 ? field.substring(4) : field;
}
