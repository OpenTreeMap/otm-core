"use strict";

var inlineEditForm = require('treemap/inlineEditForm');
var recentEdits = require('treemap/recentEdits');

exports.init = function(options) {
    inlineEditForm.init(options.inlineEditForm);
    recentEdits.init(options.recentEdits);
};
