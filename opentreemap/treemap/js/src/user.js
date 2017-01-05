"use strict";

var inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    recentEdits = require('treemap/lib/recentEdits.js'),
    uploadPanel = require('treemap/lib/uploadPanel.js'),
    csrf = require('treemap/lib/csrf.js'),
    $ = require('jquery');

$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

inlineEditForm.init({
    updateUrl: window.location.href,
    form: '#user-form',
    edit: '#edit-user',
    save: '#save-edit',
    cancel: '#cancel-edit',
    displayFields: '[data-class="display"]',
    editFields: '[data-class="edit"]',
    validationFields: '[data-class="error"]',
    errorCallback: require('treemap/lib/alerts.js').errorCallback
});

recentEdits.init({
    recentEditsContainer: '#recent-user-edits-container',
    prevLink: '#recent-user-edits-prev',
    nextLink: '#recent-user-edits-next',
});

uploadPanel.init({
    imageElement: '#user-photo'
});
