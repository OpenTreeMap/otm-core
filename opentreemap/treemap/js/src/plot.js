"use strict";

var $ = require('jquery');
var _ = require('underscore');
var otmTypeahead = require('./otmTypeahead');

var inlineEditForm = require('./inlineEditForm');

exports.init = function(options) {
    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });
    inlineEditForm.init(options.inlineEditForm);
};
