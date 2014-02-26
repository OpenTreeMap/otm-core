"use strict";
// A wrapper around twitter's typeahead library with some sane defaults

// Bootstrap must always be imported before typeahead
require('bootstrap');
require('typeahead');

var $ = require("jquery"),
    _ = require("lodash"),
    mustache = require("mustache"),
    Bacon = require("baconjs"),
    Bloodhound = require("bloodhound"),
    BU = require("treemap/baconUtils");

function eventToTargetValue(e) { return $(e.target).val(); }

function inputStream($input) {
    return $input.asEventStream('input')
                 .map(eventToTargetValue);
}

exports.getDatum = function($typeahead) {
    return $typeahead.data('datum');
};

// Creates a comparator function from a list of keys
// If the keys of two objects are equal it uses the next key in sortKeys
// If a key starts with '-' the sort order for that key is reversed
var getSortFunction = function(sortKeys) {
    sortKeys = _.map(sortKeys, function(sortKey) {
        var sign = 1;
        if (sortKey.charAt(0) === '-') {
            sign = -1;
            sortKey = sortKey.slice(1);
        }
        return {key: sortKey, sign: sign};
    });

    return function(a, b) {
        function compareKeys(key) {
            if (a[key] < b[key]) {
                return -1;
            } else if (a[key] > b[key]) {
                return 1;
            }
            return 0;
        }
        var compareVal, sortKey;
        for (var i = 0; i < sortKeys.length; i++) {
            sortKey = sortKeys[i];
            compareVal = sortKey.sign * compareKeys(sortKey.key);
            if (compareVal !== 0) {
                break;
            }
        }
        return compareVal;
    };
};

var create = exports.create = function(options) {
    var config = options.config,
        template = mustache.compile($(options.template).html()),
        $input = $(options.input),
        $hidden_input = $(options.hidden),
        $openButton = $(options.button),
        reverse = options.reverse,
        sorter = _.isArray(options.sortKeys) ? getSortFunction(options.sortKeys) : undefined,

        engine = new Bloodhound({
            name: options.name, // Used for caching
            prefetch: {
                url: options.url,
                ttl: 0 // TODO: Use high TTL and set thumbprint
            },
            limit: 3000,
            datumTokenizer: function(datum) {
                return datum.tokens;
            },
            queryTokenizer: Bloodhound.tokenizers.nonword,
            sorter: sorter
        }),

        enginePromise = engine.initialize(),

        setTypeaheadAfterDataLoaded = function($typeahead, key, query) {
            if (!key) {
                setTypeahead($typeahead, query);
            } else if (query && query.length !== 0) {
                engine.get('', function(datums) {
                    var data = _.filter(datums, function(datum) {
                            return datum[key] == query;
                        });

                    if (data.length > 0) {
                        setTypeahead($typeahead, data[0].value);
                    }
                });
            } else {
                setTypeahead($typeahead, '');
            }
        },

        setTypeahead = function($typeahead, val) {
            $typeahead.typeahead('val', val);
            $typeahead.typeahead('close');
        };


    $input.typeahead({
        minLength: options.minLength || 0
    }, {
        source: engine.ttAdapter(),
        templates: {
            suggestion: template
        },
    });

    var selectStream = $input.asEventStream('typeahead:selected typeahead:autocompleted',
                                            function(e, datum) { return datum; }),

        backspaceOrDeleteStream = $input.asEventStream('keyup')
                                        .filter(BU.keyCodeIs([8, 46])),

        editStream = selectStream.merge(backspaceOrDeleteStream.map(undefined)).skipDuplicates(),

        idStream = selectStream.map(".id")
                               .merge(backspaceOrDeleteStream.map(""));

    editStream.filter(BU.isDefined).onValue($input, "data", "datum");
    editStream.filter(BU.isUndefined).onValue($input, "removeData", "datum");

    if (options.forceMatch) {
        $input.on('blur', function() {
            if ($input.find('.tt-dropdown-menu').is(':visible')) return;

            if ($input.data('datum') === undefined) {
                setTypeahead($input, '');
            }
        });
    }
    // Set data-unmatched to the input value if the value was not
    // matched to a typeahead datum. Allows for external code to take
    // alternate action if there is no typeahead match.
    inputStream($input)
        .merge(idStream.map(""))
        .onValue($input, 'attr', 'data-unmatched');

    if (options.hidden) {
        idStream.onValue($hidden_input, "val");

        enginePromise.done(function() {
            // Specify a 'reverse' key to lookup data in reverse,
            // otherwise restore verbatim
            var value = $hidden_input.val();
            if (value) {
                setTypeaheadAfterDataLoaded($input, reverse, value);
            }
        });

        $hidden_input.on('restore', function(event, value) {
            enginePromise.done(function() {
                // If we're already loaded, this applies right away
                setTypeaheadAfterDataLoaded($input, reverse, value);
            });

            // If we're not, this will get used when loaded later
            $hidden_input.val(value || '');
        });

    }

    if (options.button) {
        var isOpen = false;
        $input.on('typeahead:opened', function() {
            isOpen = true;
        });
        $input.on('typeahead:closed', function() {
            isOpen = false;
            $openButton.removeClass('active');
        });
        $openButton.on('click', function(e) {
            e.preventDefault();
            if (isOpen) {
                $input.typeahead('close');
            } else {
                setTypeahead($input, '');
                $input.typeahead('open');

                // The open may fail if there is no data to show
                // If so don't add the active class, because then it can never
                // be removed
                if (isOpen) {
                    $openButton.addClass('active');
                }
            }
        });
    }
};

exports.bulkCreate = function (typeaheads) {
    _.each(typeaheads, create);
};
