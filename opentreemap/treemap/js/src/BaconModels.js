"use strict";

// Lightweight data models for Bacon.js. Inspired by Backbone.js.

// In short, provide:
// * an empty state definition to establish boundaries of the problem
//   space are.
// * a widgets object declaratively representing how different UI
//   elements interact. In essence, widgets provides a syntax for
//   expressing how to read data from dom elements and update the
//   state.
// * (Optional) External streams that live outside this abstraction
//   but provide stateDiff events to the global property. The most
//   common case for this is an external reset stream that pushes a
//   copy of the empty state into the stream.
//
// receive:
// a property whose value is the up-to-date state.

// state is the data abstraction used throughout this module to
// represent the global state of interdependent entities. Values
// are set to a value (including the null case) either in a state
// representation to show that the widget was/is this value, or in
// a state diff to indicate that the widget should become
// empty. In the case of null, this means removing the value.

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash');

// Bacon.js is an npm module, but only extends jQuery if it's a global object
// So we need to add extend jQuery with Bacon methods manually
$.extend($.fn, Bacon.$);

function getModifiedValue ($el, modifier, stateKey) {
    if (_.isFunction(modifier)) {
        return modifier($el, stateKey);
    } else if (_.isNull(modifier)) {
        return null;
    } else {
        return $el.attr(modifier);
    }
}

function getStateDiff (stateModifiers, $el) {
    var results = _.reduce(
            stateModifiers,
            function (acc, modifier, stateKey) {
                acc[stateKey] = getModifiedValue($el, modifier, stateKey);
                return acc;
            }, {});
    return results;
}

function makeDiffStream (widget) {
    var stateModifiers = widget.stateModifiers || {};
    return $(widget.selector)
        .asEventStream("change")
        .map('.target').map($)
        .map(getStateDiff, stateModifiers);
}

exports.getVal = function ($el) { return $el.val(); };

exports.getOptionAttr = function (attr) {
    return function ($el) {
        var value = $el.find('option:selected').attr(attr);
        if (_.isUndefined(value)) {
            value = null;
        }
        return value;
    };
};

exports.init = function (config) {
    var diffStreams = _.map(config.widgets, makeDiffStream),
        externalStreams = config.externalStreams || [],
        globalState = Bacon
            .mergeAll(diffStreams.concat(externalStreams))
            .scan(_.extend({}, config.emptyState),
                  _.partial(_.extend, {}));

    globalState.onValue(function (state) {
        _.each(config.widgets, function (widget) { widget.reset(state); });
    });

    return globalState;
};
