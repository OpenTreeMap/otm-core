"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),
    History = require('history'),

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
        History.Adapter.bind(window, 'statechange', callback);
        // We use the "History" library for "pushState" etc. capabilities on IE9.
        // If we drop IE9 support we should change "History" to "history" in this
        // module, and replace the above "bind" call with:
        //        window.onpopstate = function(event) {
        //            setStateAndPushToApp(event.state || getStateFromCurrentUrl());
        //        };
    }
    function getState() {
        return History.getState();
    }
    function pushState(state, title, url) {
        History.pushState(state, title, url);
    }
    function replaceState(state, title, url) {
        History.replaceState(state, title, url);
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

module.exports = {
    init: function (options) {
        options = _.defaults(options, {
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
        if (!_.isEqual(zoomLatLng, _state.zoomLatLng)) {
            _state.zoomLatLng = zoomLatLng;
            _history.replaceState(_state, document.title, getUrlFromCurrentState());
        }
    },

    setSearch: function (otmSearch) {
        if (!_.isEqual(otmSearch, _state.search)) {
            _state.search = otmSearch;
            _history.pushState(_state, document.title, getUrlFromCurrentState());
        }
    },

    setModeName: function (modeName) {
        modeName = _.contains(modeNamesForUrl, modeName) ? modeName : '';
        if (modeName !== _state.modeName) {
            _state.modeName = modeName;
            _history.replaceState(_state, document.title, getUrlFromCurrentState());
        }
    },

    getSearch: function() {
        return _state.search;
    },

    get: function(key) {
        return _state[key];
    },

    set: function(key, value) {
        if (!_.isEqual(_state && _state[key], value)) {
            _state[key] = value;
            _history.replaceState(_state, document.title, getUrlFromCurrentState());
        }
    },

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

function getUrlFromCurrentState() {
    var parsedUrl = url.parse(_window.getLocationHref()),
        query = {};

    _.each(_state, function(v, k) {
        var serialize = serializers[k];
        if (serialize) {
            serialize(_state, query);
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
