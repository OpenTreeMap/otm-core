'use strict';

var Bacon = require('baconjs'),
    OL = require('OpenLayers'),
    _ = require('underscore');


exports = module.exports = OL.Map.prototype.asEventStream = function(eventName) {
    var map = this,
        subscribers = [],
        dispatch = function(e) {
            _.each(subscribers, function(subscriber) {
                subscriber(new Bacon.Next(function() { return e; }));
            });
        };
    map.events.register(eventName, map, dispatch);
    return new Bacon.EventStream(function(subscriber) {
        subscribers.push(subscriber);
        return function unsubscribe() {
            subscribers = _(subscribers).reject(function (s) {
                if (s === subscriber) {
                    map.unregister(eventName, map, dispatch);
                    return true;
                } else {
                    return false;
                }
            });
        };
    });
};