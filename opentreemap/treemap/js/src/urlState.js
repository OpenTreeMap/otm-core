"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),

    modeNamesForUrl = [
        require('treemap/addTreeMode').name,
        require('treemap/addResourceMode').name,
        'prioritization',
        'scenarios'
    ];

var _state = null,
    _stateChangeBus = new Bacon.Bus(),
    _history = null,
    _window = null;

function HistoryApi() {
    function onStateChange(callback) {
        window.onpopstate = callback;
    }
    function getState() {
        return history.state;
    }
    function pushState(state, title, url) {
        history.pushState(state, title, url);
    }
    function replaceState(state, title, url) {
        history.replaceState(state, title, url);
    }
    return {
        onStateChange: onStateChange,
        getState: getState,
        pushState: pushState,
        replaceState: replaceState
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
            var zoom = state.zoomLatLng.zoom,
                precision = Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2)),
                lat = state.zoomLatLng.lat.toFixed(precision),
                lng = state.zoomLatLng.lng.toFixed(precision);
            query.z = [zoom, lat, lng].join('/');
        }
    },

    search: function(state, query) {
        if (state.search && state.search.filter && !_.isEmpty(state.search.filter)) {
            query.q = JSON.stringify(state.search.filter);
        }
        if (state.search && state.search.display) {
            query.show = JSON.stringify(state.search.display);
        }
    },

    modeName: function(state, query) {
        if (state.modeName) {
            query.m = state.modeName;
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

    m: function(newState, query) {
        newState.modeName = query.m || '';
    }
};

function set(key, value, options) {
    options = _.defaults({}, options, {
        silent: false,
        replaceState: false
    });

    var currentValue = _state && _state[key];

    if (!_.isEqual(currentValue, value)) {
        var newState = _.extend({}, _state);
        newState[key] = value;

        // Prevent data from being pushed to _stateChangeBus by making _state
        // identical to newState.
        if (options.silent) {
            _state = newState;
        }

        if (options.replaceState) {
            _history.replaceState(newState, document.title, getUrlFromState(newState));
        } else {
            _history.pushState(newState, document.title, getUrlFromState(newState));
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
            setStateAndPushToApp(_history.getState().data || getStateFromCurrentUrl());
        });
    },

    setZoomLatLng: function (zoom, center) {
        var zoomLatLng = makeZoomLatLng(zoom, center.lat, center.lng);
        set('zoomLatLng', zoomLatLng, {
            silent: true,
            replaceState: true
        });
    },

    setSearch: function (otmSearch) {
        set('search', otmSearch, {
            silent: true,
            replaceState: false
        });
    },

    setModeName: function (modeName) {
        modeName = _.contains(modeNamesForUrl, modeName) ? modeName : '';
        set('modeName', modeName, {
            silent: true,
            replaceState: true
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
    var newState = {},
        query = url.parse(_window.getLocationHref(), true).query,
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
    var changedState = _.omit(newState, function(v, k) {
        return _state && _.isEqual(_state[k], v);
    });
    _state = newState;
    if (!_.isEmpty(changedState)) {
        _stateChangeBus.push(changedState);
    }
}
