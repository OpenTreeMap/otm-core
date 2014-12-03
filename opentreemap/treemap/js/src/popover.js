"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    _ = require('lodash'),

    dom = {
        // popovers live in a detached portion of the DOM
        // that is not wrapped in any specific div. Here
        // we abstract over that implementation detail so
        // that it does not appear that events are carelessly
        // scoped to body due to programmer error.
        popupContainer: 'body',
        popupTriggers: '[data-toggle="popover"]',
        popup: {
            outermostElement: 'div.popover',
            cancelButton: '.popover-cancel',
            acceptButton: '.popover-accept',
            innerData: '.popover-data'
        }
    },

    actions = { show: 'show',
                hide: 'hide'};


// Placed onto the jquery object
require('bootstrap');

function hideAssociatedPopup(event) {
    // When this event happens, there is no link back to
    // the element who owns this popover, so we can't do
    // a simple thing like:
    // $(event.currentTarget).owner().popover(actions.hide);
    // we have to manually hide the popup.
    $(event.currentTarget).closest(dom.popup.outermostElement).hide();
}

function showPopup (event) {
    $(dom.popupTriggers).not(event.currentTarget).popover(actions.hide);
    $(event.currentTarget).popover(actions.show);
}

exports.init = function ($container) {
    $container.on('click', dom.popupTriggers, showPopup);
    $(dom.popupContainer).on('click', dom.popup.cancelButton, hideAssociatedPopup);

    var acceptStream = $(dom.popupContainer)
            .asEventStream('click', dom.popup.acceptButton);
    acceptStream.onValue(hideAssociatedPopup);
    return acceptStream;
};

exports.activateAll = function () {
    $('.popover').remove();
    _.each($(dom.popupTriggers), function (cell) {
        var $cell = $(cell),
            $data = $cell.find(dom.popup.innerData),
            data = _.isEmpty($data) ? {} : {content: $data.html(), html: true };
        $cell.popover(data);
    });
};

