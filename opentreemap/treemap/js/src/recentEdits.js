"use strict";

var $ = require('jquery');

exports.init = function(options) {
    var $recentEditsContainer = $(options.recentEditsContainer),
        links = [options.prevLink, options.nextLink].join(',');

    $recentEditsContainer.on('click', links, function(e) {
        e.preventDefault();

        $recentEditsContainer.load(this.href);
    });
};
