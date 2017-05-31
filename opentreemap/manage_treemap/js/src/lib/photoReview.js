"use strict";

var $ = require('jquery'),
    BU = require('treemap/lib/baconUtils.js'),
    batchModeration = require('manage_treemap/lib/batchModeration.js');

var csrf = require('treemap/lib/csrf.js');
$.ajaxSetup(csrf.jqueryAjaxSetupOptions);

var dom = {
    pagingButtons: '.pagination li a',
    sortHeader: '[data-photo-sort] a',
    filterButton: '[data-photo-filter] a',
};

exports.init = function(options) {
    var $container = $(options.container);

    BU.reloadContainerOnClickAndRecordUrl($container, dom.pagingButtons, dom.sortHeader, dom.filterButton);

    return batchModeration($container);
};
