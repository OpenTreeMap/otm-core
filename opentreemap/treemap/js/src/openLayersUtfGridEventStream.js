'use strict';

var Bacon = require('baconjs'),
    OL = require('OpenLayers'),
    _ = require('underscore');

exports = module.exports = OL.Control.UTFGrid.prototype.asEventStream = function(handlerMode) {
    var control = this;
    var originalCallback = control.callback || function noop() {};
    var subscribers = [];
    if (handlerMode) { control.setHandler(handlerMode); }
    control.callback = function(info) {
        originalCallback(info);
        _.each(info, function(props) {
            var data = props ? props.data : {};
            _.each(subscribers, function(subscriber) {
                subscriber(new Bacon.Next(function() { return data; }));
            });
        });
    };
    return new Bacon.EventStream(function(subscriber) {
        subscribers.push(subscriber);
        return function unsubscribe() {
            subscribers = _(subscribers).reject(function (s) {
                return s === subscriber;
            });
        };
    });
};