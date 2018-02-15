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
    var templateMarkup = $(options.template).html(),
        // As of 0.8.0 mustache no longer generates template functions. We
        // create an old style template function so that the older version of
        // typeahead does not notice the API change.
        template = function(data) {
            return mustache.render(templateMarkup, data);
        },
        $input = $(options.input),
        $hidden_input = $(options.hidden),
        reverse = options.reverse,
        sorter = _.isArray(options.sortKeys) ? getSortFunction(options.sortKeys) : getSortFunction(['value']),
        lastSelection = null,

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
            source: function(query, sync, async) {
                if (query === '') {
                    sync([]);
                } else {
                    geocoderEngine.search(query, sync, async);
                }
            },
            display: 'text'
        };

    // Parsing speeds up future, repeated usages of the template
    mustache.parse(templateMarkup);

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
            datumTokenizer: Bloodhound.tokenizers.nonword,
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
                    // Omit choices representing more than one match (e.g. "Beaches")
                    return _.filter(response.suggestions, {'isCollection': false});
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

        idStream = matchStream.map(".id").merge(backspaceOrDeleteStream.map("")),

        openCloseStream = Bacon.mergeAll(
                $input.asEventStream('focus typeahead:active typeahead:open').map(true),
                $input.asEventStream('typeahead:idle typeahead:close').map(false)
            ),

        allDataStream,

        enginePostActionBus = new Bacon.Bus();

    // Keep track of when an item is selected from the typeahead menu
    // to avoid a redundant call to `autocomplete` that could mistakenly
    // change the selected value.
    $input.on('typeahead:select', function(ev, suggestion) {
        lastSelection = suggestion.value;
    });

    selectStream.onValue(function() {
        // After the user selects a field, blur the input so that any soft
        // keyboards that are open will close (mobile)
        _.defer(function() {
            $input.trigger('blur');
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
        if (options.hidden) {
            $input.on('input', function() {
                if ($input.data('datum') === undefined) {
                    $hidden_input.val('');
                }
            });
        }
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
                enginePostActionBus.push();
            });


            $hidden_input.on('restore', function(event, value) {
                enginePromise.done(function() {
                    // If we're already loaded, this applies right away
                    setTypeaheadAfterDataLoaded($input, reverse, value);
                    enginePostActionBus.push();
                });

                // If we're not, this will get used when loaded later
                $hidden_input.val(value || '');
                enginePostActionBus.push();
            });

            allDataStream = Bacon.fromPromise(enginePromise).map(function() {
                return prefetchEngine.all();
            });
        } else if (options.remote) {
            queryEngine.initialize();
            idStream.onValue($hidden_input, 'val');
            $hidden_input.on('restore', function(event, value) {
                $hidden_input.val(value || '');
                var displayValue = $input.data('display-value');
                setTypeahead($input, displayValue || value || '');
            });
        }
    }

    return {
        autocomplete: function () {
            var top, success;
            if ($input.val()) {
                if (lastSelection === $input.val()) {
                    success = true;
                } else {
                    top = $input.data('ttTypeahead').menu.getTopSelectable();
                    success = $input.typeahead('autocomplete', top);
                }
                if (!success) {
                    $input.removeData('datum');
                }
            }
        },
        getGeocodeDatum: function(val, cb) {
            if (geocoderEngine) {
                geocoderEngine.initialize().done(function() {
                    geocoderEngine.search($input.val(), $.noop, function(datums) {
                        if (datums.length > 0) {
                            lastSelection = datums[0].text;
                            $input.data('datum', datums[0]);
                            cb(datums[0]);
                        }
                    });
                });
            }
        },
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
        input: options.input,
        selectStream: selectStream,
        programmaticallyUpdatedStream: enginePostActionBus.map(_.identity),
        allDataStream: allDataStream
    };
};

exports.bulkCreate = function(typeaheads) {
    _.each(typeaheads, create);
};
