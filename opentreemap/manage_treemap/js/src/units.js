"use strict";

var inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    alerts = require('treemap/lib/alerts.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

adminPage.init();
inlineEditForm.init({
    updateUrl: reverse.units_endpoint(config.instance.url_name) + '?update_universal_rev=1',
    section: '#units',
    errorCallback: alerts.errorCallback
});
