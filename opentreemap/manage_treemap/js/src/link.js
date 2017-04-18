"use strict";

var adminPage = require('manage_treemap/lib/adminPage.js'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js');

adminPage.init();
inlineEditForm.init({
    updateUrl: reverse.external_link(config.instance.url_name),
    section: '#external-links',
});
