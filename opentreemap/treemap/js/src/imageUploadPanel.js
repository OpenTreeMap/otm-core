"use strict";

// For modal dialog on jquery
require('bootstrap');

var $ = require('jquery');

module.exports.init = function(options) {
    addModalTrigger(options.show);
    var $form = $(options.form);
    $(options.upload).click(function() { $form.submit(); });
};

function addModalTrigger(element) {
    var $e = $(element);
    var $target = $($e.data('modal'));

    $e.click(function() {
        $target.modal('toggle');
    });
}
