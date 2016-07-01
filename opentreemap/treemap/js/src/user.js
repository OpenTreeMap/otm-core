"use strict";

var inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    recentEdits = require('treemap/lib/recentEdits.js'),
    imageUploadPanel = require('treemap/lib/imageUploadPanel.js'),
    csrf = require('treemap/lib/csrf.js'),
    $ = require('jquery');

exports.init = function(options) {
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    inlineEditForm.init(options.inlineEditForm);
    recentEdits.init(options.recentEdits);
    if (options.imageUploadPanel) {
        imageUploadPanel.init(options.imageUploadPanel);
    }
};
