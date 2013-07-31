"use strict";

// A wrapper around twitter's typeahead library with some sane defaults

require('typeahead');

var $ = require("jquery"),
    mustache = require("mustache");

exports.create = function(options) {
    var config = options.config,
        template = mustache.compile($(options.template).html()),
        $input = $(options.input),
        $hidden_input = $(options.hidden);

    $input.typeahead({
        name: options.name, // Used for caching
        prefetch: {
            url: options.url,
            ttl: 0 // TODO: Use high TTL and invalidate cache on change
        },
        limit: 10,
        template: template,
    });

    if (options.hidden) {
        $input.on('typeahead:selected typeahead:autocompleted', function($typeahead, item) {
            $hidden_input.val(item.id);
        });
    }
};
