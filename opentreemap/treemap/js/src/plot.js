"use strict";

var $ = require('jquery');
var _ = require('underscore');

// For modal dialog on jquery
require('bootstrap');

// Override typeahead from bootstrap
var otmTypeahead = require('./otmTypeahead');

var inlineEditForm = require('./inlineEditForm'),
    mapManager = require('./mapManager');

function addModalTrigger(element) {
    var $e = $(element);
    var $target = $($e.data('modal'));

    $e.click(function() {
        $target.modal('toggle');
    });
}

exports.init = function(options) {
    _.each(options.typeaheads, function(typeahead) {
        otmTypeahead.create(typeahead);
    });
    inlineEditForm.init(options.inlineEditForm);

    addModalTrigger(options.photos.show);
    var $form = $(options.photos.form);
    $(options.photos.upload).click(function() { $form.submit(); });
    
    var map = mapManager.init({
        config: options.config,
        selector: '#map',
        center: options.location,
        zoom: mapManager.ZOOM_PLOT
    });
};
