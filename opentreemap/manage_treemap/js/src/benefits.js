"use strict";

var $ = require('jquery'),
    Bacon = require('baconjs'),
    inlineEditForm = require('treemap/lib/inlineEditForm.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    alerts = require('treemap/lib/alerts.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

adminPage.init();

var form = inlineEditForm.init({
        updateUrl: reverse.benefits(config.instance.url_name),
        section: '#benefits',
        errorCallback: alerts.errorCallback
    }),

    currencyChangedStream = $('input[name="benefitCurrencyConversion.currency_symbol"]')
        .asEventStream('keyup')
        .map('.target.value'),

    currencyCanceledStream = form.cancelStream.map(function () {
        return $('[data-field="benefitCurrencyConversion.currency_symbol"][data-class="display"]')
            .attr('data-value');
    });

Bacon.mergeAll(currencyChangedStream, currencyCanceledStream)
    .onValue($('.currency-value'), 'html');
