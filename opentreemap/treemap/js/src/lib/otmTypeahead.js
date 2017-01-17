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
    BU = require("treemap/lib/baconUtils");

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
    var template = mustache.compile($(options.template).html()),
        $input = $(options.input),
        $hidden_input = $(options.hidden),
        $openButton = $(options.button),
        reverse = options.reverse,
        sorter = _.isArray(options.sortKeys) ? getSortFunction(options.sortKeys) : getSortFunction(['value']),

        setTypeaheadAfterDataLoaded = function($typeahead, key, query) {
            if (!key) {
                setTypeahead($typeahead, query);
            } else if (query && query.length !== 0) {
                var data = prefetchEngine.get([query]);

                if (data.length > 0) {
                    setTypeahead($typeahead, data[0].value);
                }
            } else {
                setTypeahead($typeahead, '');
            }
        },

        setTypeahead = function($typeahead, val) {
            $typeahead.typeahead('val', val);
        },

        prefetchEngine,
        queryEngine,
        geocoderEngine,
        allDataStream,

        typeaheadOptions = {
            minLength: options.minLength || 0
        },
        prefetchOptions = {
            limit: 3000,
            source: function(query, sync, async) {
                if (query === '') {
                    var result = prefetchEngine.all();
                    result.sort(sorter);
                    sync(result);
                } else {
                    prefetchEngine.search(query, sync, async);
                }
            },
            display: 'value',
            templates: {
                suggestion: template
            },
        },
        queryOptions = {
            source: null,
            display: options.display,
            templates: {
                suggestion: template
            },
        },
        geocoderOptions = {
            limit: 10,
            source: function (query, sync, async) {
                if (query === '') {
                    sync([]);
                } else {
                    geocoderEngine.search(query, sync, async);
                }
            },
            display: 'text'
        };

    if (options.url) {
        prefetchEngine = new Bloodhound({
            identify: function(datum) {
                return datum.id;
            },
            prefetch: {
                url: options.url,
                // Store in browser local storage with key e.g. 'species'.
                // Not using instance (e.g. 'boston/species') so data from
                // multiple instances doesn't exceed storage limit.
                cacheKey: options.name,
                // Cache buster, must be changed when data changes.
                thumbprint: $input.data('thumbprint')
            },
            datumTokenizer: function(datum) {
                return datum.tokens;
            },
            queryTokenizer: Bloodhound.tokenizers.nonword,
            sorter: sorter
        });
    } else if (options.remote) {
        queryEngine = new Bloodhound({
            identify: function(datum) {
                return datum.id;
            },
            remote: {
                url: options.remote,
                wildcard: '%Q%'
            },
            datumTokenizer: function(datum) {
                return datum.tokens;
            },
            queryTokenizer: Bloodhound.tokenizers.nonword
            // No sorter: the backend sorts it already
        });
        queryOptions.source = queryEngine;
    }

    if (options.geocoder) {
        var url = 'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/suggest?f=json';

        geocoderEngine = new Bloodhound({
            identify: function(datum) {
                return datum.magicKey;
            },
            queryTokenizer: Bloodhound.tokenizers.nonword,
            datumTokenizer: Bloodhound.tokenizers.obj.whitespace('text'),
            remote: {
                url: url,
                transform: function(response) {
                    return response.suggestions;
                },
                prepare: function(query, settings) {
                    if (options.geocoderBbox) {
                        // wkid 102100 == webmercator
                        var searchExtent = _.extend({spatialReference:{wkid:102100}}, options.geocoderBbox);
                        settings.url += '&searchExtent=' + JSON.stringify(searchExtent);
                    }

                    settings = _.extend({crossDomain: true}, settings);
                    settings.url += '&text=' + query;
                    return settings;
                }
            }
        });
    }

    if (prefetchEngine && geocoderEngine) {
        $input.typeahead(typeaheadOptions, prefetchOptions, geocoderOptions);
    } else if (prefetchEngine) {
        $input.typeahead(typeaheadOptions, prefetchOptions);
    } else if (geocoderEngine) {
        $input.typeahead(typeaheadOptions, geocoderOptions);
    } else if (queryEngine) {
        $input.typeahead(typeaheadOptions, queryOptions);
    }

    var datumGet = function(e, datum) { return datum; },
        selectStream = $input.asEventStream('typeahead:select', datumGet),

        autocompleteStream = $input.asEventStream('typeahead:autocomplete', datumGet),

        matchStream = Bacon.mergeAll(selectStream, autocompleteStream),

        backspaceOrDeleteStream = $input.asEventStream('keyup')
                                        .filter(BU.keyCodeIs([8, 46])),

        editStream = matchStream.merge(backspaceOrDeleteStream.map(undefined)),

        idStream = matchStream.map(".id")
                               .merge(backspaceOrDeleteStream.map("")),

        openCloseStream = Bacon.mergeAll(
                $input.asEventStream('focus typeahead:active typeahead:open').map(true),
                $input.asEventStream('typeahead:idle typeahead:close').map(false)
            );

    selectStream.onValue(function() {
        // After the user selects a field, blur the input so that any soft
        // keyboards that are open will close (mobile)
        _.defer(function() {
            $input.blur();
        });
    });

    editStream.filter(BU.isDefined).onValue($input, "data", "datum");
    editStream.filter(BU.isUndefined).onValue($input, "removeData", "datum");

    openCloseStream.onValue(function(active) {
            $input.closest('.search-wrapper').toggleClass('typeahead-active', active);
        });

    if (options.forceMatch) {
        $input.on('blur', function() {
            if ($input.typeahead('isOpen')) return;

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
        if (options.url) {
            var enginePromise = prefetchEngine.initialize();
            idStream.onValue($hidden_input, 'val');

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

            allDataStream = Bacon.fromPromise(enginePromise).map(function () {
                return prefetchEngine.all();
            });
        } else if (options.remote) {
            queryEngine.initialize();
            idStream.onValue($hidden_input, 'val');
            $hidden_input.on('restore', function(event, value) {
                $hidden_input.val(value || '');
                $input.val(value || '');
            });
        }
    }

    if (options.button) {
        // typeahead('open') will not show suggestions unless they have already
        // been rendered once by focusing on the text box. Doing a quick focus
        // then blur on page load means we can later call it on button click
        $input.focus();
        $input.blur();

        var isOpen = false;
        $input.on('typeahead:open', function() {
            isOpen = true;
        });
        $input.on('typeahead:close', function() {
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

    return {
        getDatum: function() {
            return exports.getDatum($input);
        },
        clear: function() {
            $input.typeahead('val', '');
            $input.removeData('datum');
            if (options.hidden) {
                $hidden_input.val('');
            }
        },
        selectStream: selectStream,
        allDataStream: allDataStream
    };
};

exports.bulkCreate = function (typeaheads) {
    _.each(typeaheads, create);
};
