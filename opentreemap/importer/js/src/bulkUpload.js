"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

adminPage.init();
require('importer/lib/importsList.js').init({
    startImportUrl: reverse['importer:start_import'](config.instance.url_name)
});
