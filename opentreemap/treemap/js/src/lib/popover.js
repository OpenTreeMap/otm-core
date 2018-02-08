"use strict";

var $ = require('jquery'),
    R = require('ramda'),
    Bacon = require('baconjs'),
    _ = require('lodash'),

    dom = {
        popupTriggers: '[data-toggle="popover"]',
        popup: {
            outermostElement: 'div.popover',
            cancelButton: '.popover-cancel',
            acceptButton: '.popover-accept',
            innerData: '.popover-data',
            input: 'input.popover-correction'
        }
    },

    actions = { show: 'show',
                hide: 'hide'};


// Placed onto the jquery object
require('bootstrap');

function hideAssociatedPopup(event) {
    $(event.currentTarget).closest(dom.popupTriggers).popover(actions.hide);
}

function showPopup (event) {
    $(dom.popupTriggers).not(event.currentTarget).popover(actions.hide);
    $(event.currentTarget).popover(actions.show);
    $(dom.popup.input).trigger('focus').trigger('select');
}

exports.init = function ($container) {
    // any click inside a popup must stop propagating because it will clash
    // with the click behavior on its container
    $container.on('click', dom.popup.outermostElement, R.invoker(0, 'stopPropagation'));
    $container.on('click', dom.popup.cancelButton, hideAssociatedPopup);
    $container.on('click', dom.popupTriggers, showPopup);

    var acceptStream = $container.asEventStream('click', dom.popup.acceptButton);
    acceptStream.onValue(hideAssociatedPopup);
    return acceptStream;
};

exports.activateAll = function () {
    $('.popover').remove();
    _.each($(dom.popupTriggers), function (cell) {
        var $cell = $(cell),
            $data = $cell.find(dom.popup.innerData),
            data = _.isEmpty($data) ? {} : {content: $data.html(),
                                            container: cell,
                                            html: true };
        $cell.popover(data);
    });
};

