"use strict";

// Manage the URL query string.
// Callers may:
// * Fetch data from the URL using get()
// * Store data in the URL using set() or custom functions like setSearch()
// * Handle events in the stateChangeStream to respond to URL changes
//
// We track in _state the current values of URL query string parameters, and use
// it when the history changes to send only changed values to the stateChangeStream.

var _ = require('lodash'),
    Bacon = require('baconjs'),
    U = require('treemap/lib/utility.js'),
    url = require('url'),

    modeNamesForUrl = [
        require('treemap/mapPage/addTreeMode.js').name,
        require('treemap/mapPage/addResourceMode.js').name
    ];

var _state = null,
    _stateChangeBus = new Bacon.Bus(),
    _history = null,
    _window = null;

function HistoryApi() {
    var stateChangeCallback = null;

    function onStateChange(callback) {
        stateChangeCallback = callback;
        window.onpopstate = callback;
    }
    function pushUrl(url) {
        history.pushState(null, document.title, url);
        if (stateChangeCallback) {
            stateChangeCallback();
        }
    }
    function replaceUrl(url) {
        history.replaceState(null, document.title, url);
        if (stateChangeCallback) {
            stateChangeCallback();
        }
    }
    return {
        onStateChange: onStateChange,
        pushUrl: pushUrl,
        replaceUrl: replaceUrl
    };
}

function WindowApi() {
    return {
        getLocationHref: function() {
            return window.location.href;
        }
    };
}

// Serialize state to query.
var serializers = {
    zoomLatLng: function(state, query) {
        if (state.zoomLatLng) {
            query.z = U.makeZoomLatLngQuery(state.zoomLatLng);
        }
    },

    search: function(state, query) {
        if (state.search && state.search.filter && !_.isEmpty(state.search.filter)) {
            query.q = JSON.stringify(state.search.filter);
        }
        if (state.search && state.search.display) {
            query.show = JSON.stringify(state.search.display);
        }
        if (state.search && state.search.address) {
            query.a = state.search.address;
        }
    },

    modeName: function(state, query) {
        if (state.modeName) {
            query.m = state.modeName;
        }
    },

    modeType: function(state, query) {
        if (state.modeType) {
            query.t = state.modeType;
        }
    }
};

// Deserialize query to newState.
var deserializers = {
    z: function(newState, query) {
        var zoomLatLng = query.z;
        newState.zoomLatLng = null;
        if (zoomLatLng) {
            var parts = zoomLatLng.split("/"),
                zoom = parseInt(parts[0], 10),
                lat = parseFloat(parts[1]),
                lng = parseFloat(parts[2]);
            if (!isNaN(zoom) && !isNaN(lat) && !isNaN(lng)) {
                newState.zoomLatLng = makeZoomLatLng(zoom, lat, lng);
            }
        }
    },

    q: function(newState, query) {
        newState.search = newState.search || {};
        newState.search.filter = JSON.parse(query.q || '{}');
    },

    show: function(newState, query) {
        newState.search = newState.search || {};
        newState.search.display = query.show ? JSON.parse(query.show) : undefined;
    },

    a: function(newState, query) {
        newState.search = newState.search || {};
        newState.search.address = query.a || undefined;
    },

    m: function(newState, query) {
        newState.modeName = query.m || '';
    },

    t: function(newState, query) {
        newState.modeType = query.t || '';
    }
};

function set(key, value, options) {
    options = _.defaults({}, options, {
        silent: false,
        replace: false
    });

    var currentValue = _state && _state[key];

    if (!_.isEqual(currentValue, value)) {
        var newState = _.extend({}, _state);
        newState[key] = value;

        // Serialize and deserialize state to ensure that deserializing state
        // from the URL will match the stored state (mostly matter for float precision)
        newState = getStateFromUrl(getUrlFromState(newState));

        // Prevent data from being pushed to _stateChangeBus by making _state
        // identical to newState.
        if (options.silent) {
            _state = newState;
        }

        if (options.replace) {
            _history.replaceUrl(getUrlFromState(newState));
        } else {
            _history.pushUrl(getUrlFromState(newState));
        }
    }
}

module.exports = {
    init: function (options) {
        options = _.defaults({}, options, {
            historyApi: new HistoryApi(),
            windowApi: new WindowApi()
        });

        _state = null;
        _history = options.historyApi;
        _window = options.windowApi;

        setStateAndPushToApp(getStateFromCurrentUrl());

        _history.onStateChange(function() {
            setStateAndPushToApp(getStateFromCurrentUrl());
        });
    },

    setZoomLatLng: function (zoomLatLng) {
        if (!_.isEmpty(zoomLatLng)) {
            set('zoomLatLng', zoomLatLng, {
                silent: true,
                replace: true
            });
        }
    },

    setSearch: function (otmSearch) {
        set('search', otmSearch, {
            silent: true,
            replace: false
        });
    },

    setModeName: function (modeName) {
        modeName = _.includes(modeNamesForUrl, modeName) ? modeName : '';
        set('modeName', modeName, {
            silent: true,
            replace: true
        });
    },

    setModeType: function (modeType) {
        set('modeType', modeType, {
            silent: true,
            replace: true
        });
    },

    getSearch: function() {
        return _state.search;
    },

    get: function(key) {
        return _state[key];
    },

    set: set,

    // TODO: Rename to changeStream.
    stateChangeStream: _stateChangeBus.map(_.identity)
};

function getStateFromCurrentUrl() {
    return getStateFromUrl(_window.getLocationHref());
}

function getStateFromUrl(urlText) {
    var newState = {},
        query = url.parse(urlText, true).query,
        allKeys = _.union(_.keys(deserializers), _.keys(query));

    _.each(allKeys, function(k) {
        var deserialize = deserializers[k];
        if (deserialize) {
            deserialize(newState, query);
        } else {
            newState[k] = query[k];
        }
    });

    return newState;
}

function makeZoomLatLng(zoom, lat, lng) {
    return { zoom: zoom, lat: lat, lng: lng };
}

function getUrlFromState(state) {
    var parsedUrl = url.parse(_window.getLocationHref()),
        query = {};

    _.each(state, function(v, k) {
        var serialize = serializers[k];
        if (serialize) {
            serialize(state, query);
        } else {
            query[k] = v;
        }
    });

    parsedUrl.query = query;
    parsedUrl.search = null;
    var urlText = url.format(parsedUrl).replace(/%2F/g, '/');
    return urlText;
}

function setStateAndPushToApp(newState) {
    var changedState = _.omitBy(newState, function(v, k) {
        return _state && _.isEqual(_state[k], v);
    });
    _state = newState;
    if (!_.isEmpty(changedState)) {
        _stateChangeBus.push(changedState);
    }
}
