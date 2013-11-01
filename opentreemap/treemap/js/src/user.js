"use strict";

var inlineEditForm = require('treemap/inlineEditForm'),
    recentEdits = require('treemap/recentEdits'),
    imageUploadPanel = require('treemap/imageUploadPanel'),
    csrf = require('treemap/csrf'),
    $ = require('jquery');

exports.init = function(options) {
    $.ajaxSetup(csrf.jqueryAjaxSetupOptions);

    inlineEditForm.init(options.inlineEditForm);
    recentEdits.init(options.recentEdits);
    if (options.imageUploadPanel) {
        imageUploadPanel.init(options.imageUploadPanel);
    }
};
