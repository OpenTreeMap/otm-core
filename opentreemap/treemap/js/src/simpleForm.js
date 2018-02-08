"use strict";

var $ = require('jquery');

$(function () {
    $('input[type!="hidden"]').first().trigger('focus');
});
