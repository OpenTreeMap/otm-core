"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    uploadPanel = require('treemap/lib/uploadPanel.js'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    url = require('url'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    alerts = require('treemap/lib/alerts.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

require('jscolor');

var dom = {
    colorInput: {
        primary: 'input[name="instance.config.scss_variables.primary-color"]',
        secondary: 'input[name="instance.config.scss_variables.secondary-color"]'
    },
    colorDisplay: {
        primary: '[data-field="instance.config.scss_variables.primary-color"][data-class="display"]',
        secondary: '[data-field="instance.config.scss_variables.secondary-color"][data-class="display"]',
    },
    useDefaultColors: '.js-use-default-colors',
    linkSelector: '#application-css',
    uploadPanel: {
        imageElement: '#site-logo'
    }
};

adminPage.init();

var cssUrl = reverse.scss() + '?' + config.instance.scssQuery,
    form = inlineEditForm.init({
        updateUrl: reverse.branding(config.instance.url_name),
        section: '#branding',
        errorCallback: alerts.errorCallback
    });

uploadPanel.init(dom.uploadPanel);

$(dom.useDefaultColors).on('click', function () {
    setColor(dom.colorInput.primary, '8BAA3D');
    setColor(dom.colorInput.secondary, '56ABB2');
});

form.cancelStream.onValue(function () {
    setColor(dom.colorInput.primary, $(dom.colorDisplay.primary).attr('data-value'));
    setColor(dom.colorInput.secondary, $(dom.colorDisplay.secondary).attr('data-value'));
});

function setColor(selector, value) {
    $(selector)[0].color.fromString(value);
}

// On save update the CSS url to use the new colors
form.saveOkStream
    .map('.formData')
    .map(function (fieldDictionary) {
        var cssUrlObject = url.parse(cssUrl, true),
            query = _.reduce(fieldDictionary, function (query, value, name) {
                var field = name.split(".").pop();
                if (value) {
                    query[field] = value;
                }
                return query;
            }, cssUrlObject.query);
        cssUrlObject.search = null;  // Force url.format to parse query object
        cssUrl = url.format(cssUrlObject);
        return cssUrl;
    })
    .onValue($(dom.linkSelector), 'attr', 'href');
