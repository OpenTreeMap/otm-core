"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse'),
    format = require('util').format,
    Bacon = require('baconjs');

adminPage.init();

// constants
var $iframeSizeCustom = $('#frame-size-custom'),
    $iframeWidth = $('#iframe-width'),
    $iframeHeight = $('#iframe-height'),
    $previewButton = $('#preview'),
    $snippet = $('#snippet'),
    $iframeContainer = $('#iframe-container'),
    $sizeChoiceRadio = $('input[name="frame-size"]'),
    $alerts = $('.alert'),
    $messages = $('.message');

// mutable state
var errors = [],
    isCustom = false,
    curSnippet = $snippet.val();

// utility functions
var focusSelectSnippet = function () {
    if (!_.isEmpty($snippet.val())) {
        $snippet.trigger('focus').trigger('select');
    }
};

var validateCustom = function () {
    var errors = [],
        w = $iframeWidth.val(),
        h = $iframeHeight.val();

    if (_.isEmpty(w) && _.isEmpty(h)) {
        errors.push('both-required');
    } else if (_.isEmpty(w)) {
        errors.push('width-required');
    } else if (_.isEmpty(h)) {
        errors.push('height-required');
    }

    var wOutOfRange = false,
        hOutOfRange = false;

    if (!_.isEmpty(w)) {
        w = parseInt(w, 10);
        wOutOfRange = w < 768 || 10000 < w;
    }
    if (!_.isEmpty(h)) {
        h = parseInt(h, 10);
        hOutOfRange = h < 450 || 10000 < h;
    }

    if (wOutOfRange && hOutOfRange) {
        errors.push('both-range-error');
    } else if (wOutOfRange) {
        errors.push('width-range-error');
    } else if (hOutOfRange) {
        errors.push('height-range-error');
    }

    return errors;
};

var validate = function ($target) {
    return isCustom ? validateCustom() : [];
};

var formatCustomSnippet = function () {
    return format($iframeSizeCustom.val(),
                  $iframeWidth.val(), $iframeHeight.val());
};

var fetchSnippet = function ($target) {
    if (!isCustom) {
        return $target.val();
    } else if (_.isEmpty(errors)) {
        return formatCustomSnippet();
    } else {
        return '';
    }
};

var hideMessages = function () {
    $messages.addClass('hidden');
    $alerts.addClass('hidden');
};

var showMessages = function (errorIds) {
    if (!_.isEmpty(errorIds)) {
        var selectors = _.map(errorIds, function (id) {
            return '#' + id;
        }).join(',');
        $(selectors).removeClass('hidden');
        $alerts.removeClass('hidden');
    }
};

var updateDisplay = function () {
    hideMessages();
    $snippet.val(curSnippet);
    focusSelectSnippet();
    $iframeContainer.empty();
    if (!isCustom) {
        $iframeContainer.html(curSnippet);
    }
};

var handleChoice = function (ev) {
    isCustom = $iframeSizeCustom.get(0) === ev.target;
    var $target = $(ev.target);

    errors = validate($target);
    curSnippet = fetchSnippet($target);
    updateDisplay();
};

$sizeChoiceRadio.on('change', handleChoice);

var doPreview = function (ev) {
    ev.preventDefault();
    errors = validateCustom();
    curSnippet = fetchSnippet($iframeSizeCustom);
    updateDisplay();
    $iframeContainer.html(curSnippet);
    showMessages(errors);
};

$previewButton.on('click', doPreview);

focusSelectSnippet();
