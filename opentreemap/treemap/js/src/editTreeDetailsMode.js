"use strict";

var _ = require('underscore'),
    otmTypeahead = require('./otmTypeahead');

var map,
    inlineEditForm;

function init(options) {
    map = options.map;
    inlineEditForm = options.inlineEditForm;

    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });
}

function activate() {
}

function deactivate() {
}

module.exports = {
    init: init,
    activate: activate,
    deactivate: deactivate
};

