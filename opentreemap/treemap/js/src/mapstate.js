"use strict";

var _ = require('underscore'),
    Bacon = require('baconjs'),
    url = require('url'),
    L = require('leaflet'),
    addTreeModeName = require('./addTreeMode').name ;

var state,
    stateChangeBus = new Bacon.Bus();

module.exports = {
    init: function () {
        var defaultState = {
                zoomLatLng: null,
                search: {},
                modeName: ''
            },
            initialState = getStateFromCurrentUrl(defaultState);
        setStateAndPushToApp(initialState);
        history.replaceState(state, '', getUrlFromCurrentState());

        window.onpopstate = function(event) {
            setStateAndPushToApp(event.state || getStateFromCurrentUrl());
        };
    },

    setZoomLatLng: function (zoom, center) {
        var zoomLatLng = makeZoomLatLng(zoom, center.lat, center.lng);
        if (!_.isEqual(zoomLatLng, state.zoomLatLng)) {
            state.zoomLatLng = zoomLatLng;
            history.replaceState(state, '', getUrlFromCurrentState());
        }
    },

    setSearch: function (otmSearch) {
        if (!_.isEqual(otmSearch, state.search)) {
            state.search = otmSearch;
            history.pushState(state, '', getUrlFromCurrentState());
        }
    },

    setModeName: function (modeName) {
        // We only want "Add Tree" mode in the url
        modeName = (modeName === addTreeModeName ? modeName : '')
        if (modeName !== state.modeName) {
            state.modeName = modeName;
            history.replaceState(state, '', getUrlFromCurrentState());
        }
    },

    getSearch: function() {
        return state.search;
    },

    stateChangeStream: stateChangeBus.map(_.identity)
};

function getStateFromCurrentUrl(defaultState) {
    var newState = defaultState || {},
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
