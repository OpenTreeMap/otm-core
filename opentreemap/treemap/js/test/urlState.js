"use strict";

var assert = require('chai').assert,
    _ = require('lodash'),
    urlState = require('treemap/urlState');


function HistoryApiMock() {
    var _state = null,
        _url = '',
        _callbacks = [];

    function onStateChange(callback) {
        _callbacks.push(callback);
    }

    function getState() {
        return {
            data: _state
        };
    }

    // Exists on mock only.
    function getStateUrl() {
        return _url;
    }

    function pushState(state, title, url) {
        _state = state;
        _url = url;
        _.invoke(_callbacks, 'apply');
    }

    return {
        onStateChange: onStateChange,
        getState: getState,
        getStateUrl: getStateUrl,
        pushState: pushState,
        replaceState: pushState
    };
}


function WindowApiMock() {
    var _href = '';
    return {
        getLocationHref: function() {
            return _href;
        },
        // Exists on mock only.
        setLocationHref: function(value) {
            _href = value;
        }
    };
}


function createContext() {
    var win = new WindowApiMock(),
        history = new HistoryApiMock();

    history.onStateChange(function() {
        win.setLocationHref(history.getStateUrl());
    });

    return {
        historyApi: history,
        windowApi: win
    };
}


var historyApiMockTests = {
    'pushState': function(done) {
        var history = new HistoryApiMock();
        assert.equal(history.getState().data, null);

        history.onStateChange(function() {
            assert.deepEqual(history.getState().data, {foo: 1});
            assert.equal(history.getStateUrl(), '?foo=1');
            done();
        });

        history.pushState({foo: 1}, '', '?foo=1');
    }
};

var windowApiMockTests = {
    'getLocationHref': function() {
        var win = new WindowApiMock();
        win.setLocationHref('foo');
        assert.equal(win.getLocationHref(), 'foo');
    }
};

var urlStateTests = {
    'getters/setters': function() {
        var context = createContext();
        urlState.init(context);

        urlState.setZoomLatLng(1, {lat: 2, lng: 3});
        urlState.setModeName('scenarios');
        urlState.set('foo', 'bar');

        assert.equal(urlState.get('foo'), 'bar');
        assert.equal(context.windowApi.getLocationHref(), '?z=1/2/3&m=scenarios&foo=bar');
    },

    'stateChangeStream': function(done) {
        var context = createContext();
        context.windowApi.setLocationHref('?m=scenarios&foo=bar');
        urlState.stateChangeStream.onValue(function(state) {
            // Test state was initialized from URL.
            assert.equal(state.modeName, 'scenarios');
            assert.equal(state.foo, 'bar');

            // Predefined (aka magic) keys are also initialized with
            // a null value even if they do not appear in the URL.
            assert.equal(state.zoomLatLng, null);
            assert.notEqual(state.search, null);
            assert.equal(state.search.display, undefined);
            assert.notEqual(state.search.filter, null);

            done();
        });
        urlState.init(context);
    }
};

module.exports = {
    'treemap/urlState historyApiMockTests': historyApiMockTests,
    'treemap/urlState windowApiMockTests': windowApiMockTests,
    'treemap/urlState': urlStateTests
};
