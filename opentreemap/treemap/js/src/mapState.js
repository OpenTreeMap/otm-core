"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),
    History = require('history');

var state,
    stateChangeBus = new Bacon.Bus(),
    modeNamesForUrl = [
        require('treemap/addTreeMode').name,
        require('treemap/addResourceMode').name
    ];

module.exports = {
    init: function () {
        setStateAndPushToApp(getStateFromCurrentUrl());

        History.Adapter.bind(window, 'statechange', function() {
            setStateAndPushToApp(History.getState().data || getStateFromCurrentUrl());
        });
// We use the "History" library for "pushState" etc. capabilities on IE9.
// If we drop IE9 support we should change "History" to "history" in this
// module, and replace the above "bind" call with:
//        window.onpopstate = function(event) {
//            setStateAndPushToApp(event.state || getStateFromCurrentUrl());
//        };
    },

    setZoomLatLng: function (zoom, center) {
        var zoomLatLng = makeZoomLatLng(zoom, center.lat, center.lng);
        if (!_.isEqual(zoomLatLng, state.zoomLatLng)) {
            state.zoomLatLng = zoomLatLng;
            History.replaceState(state, document.title, getUrlFromCurrentState());
        }
    },

    setSearch: function (otmSearch) {
        if (!_.isEqual(otmSearch, state.search)) {
            state.search = otmSearch;
            History.pushState(state, document.title, getUrlFromCurrentState());
        }
    },

    setModeName: function (modeName) {
        // We only want "Add Tree" mode in the url
        modeName = (_.contains(modeNamesForUrl, modeName) ? modeName : '');
        if (modeName !== state.modeName) {
            state.modeName = modeName;
            History.replaceState(state, document.title, getUrlFromCurrentState());
        }
    },

    getSearch: function() {
        return state.search;
    },

    stateChangeStream: stateChangeBus.map(_.identity)
};

function getStateFromCurrentUrl() {
    var newState = {},
        query = url.parse(window.location.href, true).query,
        zoomLatLng = query.z;
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
    newState.search = JSON.parse(query.q || '{}');
    newState.modeName = query.m || '';
    return newState;
}

function makeZoomLatLng(zoom, lat, lng) {
    return { zoom: zoom, lat: lat, lng: lng };
}

function getUrlFromCurrentState() {
    var parsedUrl = url.parse(window.location.href),
        query = {};
    if (state.zoomLatLng) {
        var zoom = state.zoomLatLng.zoom,
            precision = Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2)),
            lat = state.zoomLatLng.lat.toFixed(precision),
            lng = state.zoomLatLng.lng.toFixed(precision);
        query.z = [zoom, lat, lng].join('/');
    }
    if (state.search && !_.isEmpty(state.search)) {
        query.q = JSON.stringify(state.search);
    }
    if (state.modeName) {
        query.m = state.modeName;
    }
    parsedUrl.query = query;
    parsedUrl.search = null;
    var urlText = url.format(parsedUrl).replace(/%2F/g, '/');
    return urlText;
}

function setStateAndPushToApp(newState) {
    var changedState = {};
    if (!state || !_.isEqual(newState.zoomLatLng, state.zoomLatLng)) {
        changedState.zoomLatLng = newState.zoomLatLng;
    }
    if (!state || !_.isEqual(newState.search, state.search)) {
        changedState.search = newState.search;
    }
    if (!state || newState.modeName !== state.modeName) {
        changedState.modeName = newState.modeName;
    }
    state = newState;
    if (!_.isEmpty(changedState)) {
        stateChangeBus.push(changedState);
    }
}
