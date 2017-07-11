"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js');

var dom = {
    mapPopover: '#map .map-popover',
    content: '#map .map-popover .content',
    closeButton: '#map .map-popover .close',
    cancelButton: '#map .map-popover .cancel-action',
    doneButton: '#map .map-popover .done'
};

var _buttonSelectors = {
        cancel: dom.cancelButton,
        close: dom.closeButton,
        done: dom.doneButton
    },
    _streams = null,  // object mapping buttonType -> stream
    _clickStream = null;

function show(message, interaction, buttonTypes) {
    buttonTypes = buttonTypes || ['cancel'];

    initStreams();

    interaction.onEnd(hide);

    _.each(_buttonSelectors, function (selector, buttonType) {
        $(selector).toggleClass('hidden', !_.includes(buttonTypes, buttonType));
    });

    $(dom.content).html(message);
    $(dom.mapPopover).fadeIn();

    return _.pick(_streams, buttonTypes);
}

function initStreams() {
    if (!_streams) {
        _streams = _.mapValues(_buttonSelectors, initClickStream);
        _clickStream = Bacon.mergeAll(_.values(_streams));
    }

    function initClickStream(buttonSelector) {
        return $(buttonSelector)
            .asEventStream('click')
            .doAction('.preventDefault');
    }
}

function hide() {
    // Cancel fadeIn animation and hide notification.
    $(dom.mapPopover).stop(true).hide();
}

module.exports = {
    show: show,
    hide: hide
};
