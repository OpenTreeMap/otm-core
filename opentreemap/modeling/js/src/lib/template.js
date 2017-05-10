"use strict";

var $ = require('jquery'),
    _ = require('lodash');

module.exports = {
    render: render
};

function render(templateName, bindings) {
    var template = getTemplate(templateName);
    return template(bindings);
}

var getTemplate = _.memoize(function(templateName) {
    return _.template($(templateName).html());
});
