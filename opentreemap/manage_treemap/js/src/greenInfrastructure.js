"use strict";

var inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    alerts = require('treemap/lib/alerts.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),
    $ = require('jquery');


adminPage.init();

var form = inlineEditForm.init({
    updateUrl: reverse.green_infrastructure(config.instance.url_name),
    section: '#gsi',
    errorCallback: alerts.errorCallback
});
form.saveOkStream.onValue(function () {
    location.reload(false);
});
$('[data-toggle="tooltip"]').tooltip();
