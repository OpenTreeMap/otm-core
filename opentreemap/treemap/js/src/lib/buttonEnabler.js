"use strict";

// A button or anchor provides:
//     disabled="disabled": it should start disabled
//     data-always-enable: true if it should always be enabled
//     data-href: the URL that will either be a direct link or a "next=" after login
//     data-disabled-title (optional) = a title to set on the disabled element
//
// If data-always-enable is true, enable the button/anchor.
// If it's false then check config.loggedIn and determine whether to
// modify the button or anchor into a loginUrl redirector or to
// leave disabled and set the disabled text.
//
// When an anchor tag gets enabled, its href is set to its data-href.

var $ = require('jquery'),
    _ = require('lodash'),
    format = require('util').format,

    enablePermAttr = 'data-always-enable',
    disabledTitleAttr = 'data-disabled-title',
    redirectUrlAttr = 'data-redirect-url',
    hrefAttr = 'data-href',
    enablePermSelector = '[' + enablePermAttr + ']',
    disabledButtonWrapperAttrPair = 'data-class="disabled-button-wrapper"',
    disabledButtonWrapperSelector = '[' + disabledButtonWrapperAttrPair + ']',
    config;

function removeActionableDataAttributes($el) {
    // in case it triggers a modal
    $el.removeAttr('data-target');
    // in case an event is bound to this element
    $el.removeAttr('data-action');
}

function makeRedirectToLogin(loginUrl, $el, href) {

    var fullHref = loginUrl + href;

    $el.attr('disabled', false);
    removeActionableDataAttributes($el);

    if ($el.is('a')) { $el.attr('href', fullHref); }
    else if ($el.is('button')) {
        $el.off('click');
        $el.click(function () {
            window.location = fullHref;
        });
    }
}

function fullyEnable($el, href) {
    $el.attr('disabled', false);
    if ($el.is('a')) { $el.attr('href', href); }
}

function fullyDisable($el, disabledTitle) {
    var wrapperTemplate =
            '<label ' + disabledButtonWrapperAttrPair +
            ' title="%s"></label>';

    $el.off('click');
    removeActionableDataAttributes($el);
    if (disabledTitle && !$el.parent().is(disabledButtonWrapperSelector)) {
        $el.wrap(format(wrapperTemplate, disabledTitle));
    }
}

exports.run = function (options) {
    var $elements = $(enablePermSelector),
        config = options.config;

    _.each($elements, function(element) {
        var $element = $(element),
            hasPerm = $element.attr(enablePermAttr),
            disabledTitle = $element.attr(disabledTitleAttr),
            href = $element.attr(hrefAttr);

        if (hasPerm === 'True') {
            fullyEnable($element, href);
        } else if (!config.loggedIn) {
            makeRedirectToLogin(config.loginUrl, $element, href);
        } else {
            fullyDisable($element, disabledTitle);
        }
    });
};
