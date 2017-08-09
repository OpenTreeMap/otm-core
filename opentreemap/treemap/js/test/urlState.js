"use strict";

var assert = require('chai').assert,
    _ = require('lodash'),
    urlState = require('treemap/lib/urlState.js');


function HistoryApiMock() {
    var _url = '',
        _callbacks = [];

    function onStateChange(callback) {
        _callbacks.push(callback);
    }

    // Exists on mock only.
    function getUrl() {
        return _url;
    }

    function pushUrl(url) {
        _url = url;
        _.invokeMap(_callbacks, 'apply');
    }

    return {
        onStateChange: onStateChange,
        getUrl: getUrl,
        pushUrl: pushUrl,
        replaceUrl: pushUrl
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
        win.setLocationHref(history.getUrl());
    });

    return {
        historyApi: history,
        windowApi: win
    };
}


var historyApiMockTests = {
    'pushUrl': function(done) {
        var history = new HistoryApiMock();
        assert.equal(history.getUrl(), '');

        history.onStateChange(function() {
            assert.equal(history.getUrl(), '?foo=1');
            done();
        });

        history.pushUrl('?foo=1');
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

        urlState.setZoomLatLng({zoom: 1, lat: 2, lng: 3});
        urlState.setModeName('addTree');
        urlState.set('foo', 'bar');

        assert.equal(urlState.get('foo'), 'bar');
        assert.equal(context.windowApi.getLocationHref(), '?z=1/2/3&m=addTree&foo=bar');
    },

    'stateChangeStream': function(done) {
        var context = createContext();
        context.windowApi.setLocationHref('?m=addTree&foo=bar');
        urlState.stateChangeStream.take(1).onValue(function(state) {
            // Test state was initialized from URL.
            assert.equal(state.modeName, 'addTree');
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
    },

    'silent mode': function(done) {
        var context = createContext();
        urlState.init(context);
        urlState.stateChangeStream.take(1).onValue(function(state) {
            assert.deepEqual(state, {bar: '2'});
            done();
        });
        // This should NOT trigger an update on stateChangeStream.
        urlState.set('foo', '1', {
            silent: true
        });
        // This SHOULD trigger an update on stateChangeStream.
        urlState.set('bar', '2', {
            silent: false
        });
    }
};

module.exports = {
    'treemap/urlState historyApiMockTests': historyApiMockTests,
    'treemap/urlState windowApiMockTests': windowApiMockTests,
    'treemap/urlState': urlStateTests
};
