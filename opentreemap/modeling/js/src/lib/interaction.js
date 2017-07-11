"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs');

// This represents a single cancelable UI interaction.
//
// The intended use case is for when you have multiple components that can
// cancel each other out. Calling `stop()` is the signal that the overall
// UI interaction is complete and all components should end.
//
// Usage:
//
//   1. Pass an instance of `Interaction` to each component.
//   2. Component calls `stop()` when it has completed its UI action.
//   3. Components can listen to `doneStream.onEnd` to handle cleanup.
//
// Example:
//
//     var interaction = new Interaction(),
//         a = clickSaveButtonStream().takeWhile(interaction.inProgress),
//         b = clickCancelButtonStream().takeWhile(interaction.inProgress);
//     a.onValue(function() { save(); interaction.stop(); });
//     b.onValue(function() { interaction.stop(); });
//     interaction.onEnd(hideSaveDialog);
//
function Interaction() {
    var bus = new Bacon.Bus(),
        inProgress = bus.toProperty(true);

    var stop = function() {
        bus.push(false);
        bus.end();
    };

    var onEnd = function(fn) {
        bus.onEnd(fn);
    };

    return {
        inProgress: inProgress,
        onEnd: onEnd,
        stop: stop
    };
}

module.exports = Interaction;
