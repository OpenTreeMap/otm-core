"use strict";

var _ = require("underscore");
// A wrapper around twitter's typeahead library with some sane defaults

// Bootstrap must always be imported before typeahead
require('bootstrap');
require('typeahead');

var $ = require("jquery"),
    mustache = require("mustache"),
    Bacon = require("baconjs"),
    keyCodeIs = require("./baconUtils").keyCodeIs;


function setTypeahead($typeahead, val) {
    $typeahead.typeahead('setQuery', val);
}

function setTypeaheadAfterDataLoaded($typeahead, key, query) {
    if (!key) {
        setTypeahead($typeahead, query);
    } else if (query && query.length !== 0) {
        var data = _.filter(
            $typeahead.data('ttView').datasets[0].itemHash,
            function(data) {
                return data.datum[key] == query;
            });

        if (data.length > 0) {
            setTypeahead($typeahead, data[0].value);
        }
    } else {
        setTypeahead($typeahead, '');
    }
}

function eventToTargetValue(e) { return $(e.target).val(); }

function inputProperty($input) {
    return $input.asEventStream('input')
                 .map(eventToTargetValue)
                 .toProperty();
}


function firstIfSecondIsEmptyElseEmpty (first, second) {
    return second === "" ? first : "";
}

exports.getDatum = function($typeahead) {
    return $typeahead.data('datum');
};

exports.create = function(options) {
    var config = options.config,
        template = mustache.compile($(options.template).html()),
        $input = $(options.input),
        $hidden_input = $(options.hidden),
        $openButton = $(options.button),
        reverse = options.reverse;

    $input.typeahead({
        name: options.name, // Used for caching
        prefetch: {
            url: options.url,
            ttl: 0 // TODO: Use high TTL and invalidate cache on change
        },
        limit: 1000,
        template: template,
        minLength: 0
    });

    var selectStream = $input.asEventStream('typeahead:selected typeahead:autocompleted',
                                            function(e, datum) { return datum; }),

        backspaceOrDeleteStream = $input.asEventStream('keyup')
                                        .filter(keyCodeIs([8, 46])),

        editStream = selectStream.merge(backspaceOrDeleteStream.map(undefined)),

        idStream = selectStream.map(".id")
                                .merge(backspaceOrDeleteStream.map(""));

    editStream.onValue($input, "data", "datum");

    // Set data-unmatched to the input value if the value was not
    // matched to a typeahead datum. Allows for external code to take
    // alternate action if there is no typeahead match.
    inputProperty($input)
        .combine(idStream.toProperty("").skipDuplicates(),
                 firstIfSecondIsEmptyElseEmpty)
        .onValue($input, 'attr', 'data-unmatched');

    if (options.hidden) {
        idStream.onValue($hidden_input, "val");


        // Specify a 'reverse' key to lookup data in reverse,
        // otherwise restore verbatim
        $input.asEventStream('typeahead:initialized')
            .onValue(function () {
                var value = $hidden_input.val();
                if (value) {
                    setTypeaheadAfterDataLoaded($input, reverse, value);
                }
            });



        $hidden_input.on('restore', function(event, value) {
            // If we're already loaded, this applies right away
            setTypeaheadAfterDataLoaded($input, reverse, value);

            // If we're not, this will get used when loaded later
            $hidden_input.val(value || '');
        });

    }

    if (options.button) {
        $openButton.on('click', function(e) {
            e.preventDefault();
            if ($input.typeahead('isOpen')) {
                $input.typeahead('close');
            } else {
                setTypeahead($input, '');
                $input.typeahead('open');

                // The open may fail if there is no data to show
                // If so don't add the active class, because then it can never
                // be removed
                if ($input.typeahead('isOpen')) {
                    $openButton.addClass('active');
                }
            }
        });
        $input.on('typeahead:closed', function() {
            $openButton.removeClass('active');
        });
    }
};
