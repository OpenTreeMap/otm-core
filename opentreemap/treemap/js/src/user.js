"use strict";

var $ = require('jquery');

exports.init = function(options) {
    var $container = $(options.container),
        links = [options.prevLink, options.nextLink].join(',');

    $container.on('click', links, function(e) {
        e.preventDefault();

        $container.load(this.href);
    });
};
