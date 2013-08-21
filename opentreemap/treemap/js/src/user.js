"use strict";

var inlineEditForm = require('./inlineEditForm');
var recentEdits = require('./recentEdits');

exports.init = function(options) {
    inlineEditForm.init(options.inlineEditForm);
    recentEdits.init(options.recentEdits);
};