"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    mustache = require('mustache');

var fieldErrorsTemplate = $('#field-error-template').html();
var globalErrorsTemplate = $('#global-errors-template').html();

// Parsing speeds up future, repeated usages of the template
mustache.parse(fieldErrorsTemplate);
mustache.parse(globalErrorsTemplate);

module.exports.convertErrorObjectIntoHtml = function (rawErrorObject) {
    var errorObject = JSON.parse(rawErrorObject.responseText),
        cleanFieldErrors = _.map(errorObject.fieldErrors, function(msgs, field) {
            return {field: stripUdfPrefix(field), message: msgs};
        }),
        cleanErrorObject = {
            errors: cleanFieldErrors,
            globalErrors: errorObject.globalErrors
        },
        globalErrorHtml = mustache.render(globalErrorsTemplate, cleanErrorObject),
        fieldErrorHtml = mustache.render(fieldErrorsTemplate, cleanErrorObject);

    return globalErrorHtml + fieldErrorHtml;
};

function stripUdfPrefix(field) {
    return field.indexOf('udf.') === 0 ? field.substring(4) : field;
}
