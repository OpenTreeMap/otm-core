"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash');

// Provides a simple helper with some internal state for determining
// if one of the many cancel events has been triggered on a bootstrap
// modal.
//
// This module exists because the events provided by bs modals are too
// general, they identify when show/hide-like events happen, but make
// it hard to distinguish between cancel and confirmation states.
//
// This module gathers all hide events, except those that are the result
// of an 'ok' click, as provided by the okStream option. It does this by
// setting an internal variable when the ok-click happens and clearing it
// once the modal is shown (again).

module.exports.init = function (opts) {
    var state = {okClick: false };

    $(opts.modalSelector)
        .asEventStream('shown.bs.modal')
        .onValue(function () { state.okClick = false; });
    opts.okStream
        .onValue(function () { state.okClick = true; });

    return $(opts.modalSelector)
        .asEventStream('hidden.bs.modal')
        .filter(function () { return !state.okClick; });
};
