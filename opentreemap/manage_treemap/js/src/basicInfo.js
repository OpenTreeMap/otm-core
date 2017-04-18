"use strict";

var adminPage = require('manage_treemap/lib/adminPage.js'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    alerts = require('treemap/lib/alerts.js'),
    reverse = require('reverse'),
    config = require('treemap/lib/config.js');

adminPage.init();
inlineEditForm.init({
    updateUrl: reverse.site_config(config.instance.url_name),
    section: '#basic-info',
});
