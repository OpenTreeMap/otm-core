"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    format = require('util').format,
    moment = require('moment'),

    udfRowTemplate = _.template(
        '<tr data-value-id="">' +
            '<% _.each(fields, function (field) { %>' +
            '<td data-value="<%= field.value %>"> <%= field.display %> </td>' +
            '<% }) %>' +
            '<td></td>' +
            '</tr>'),

    resolveButtonMarkup = '<a href="javascript:;" ' +
        'class="btn btn-mini resolveBtn" data-class="edit">Resolve</a>';

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(form) {

    function markTargetAsResolved (event) {
        var $el = $(event.target),
            $resolvedContainer = $el.closest('tr')
                .find('td:contains("Unresolved")');
        $resolvedContainer.text('Resolved');
        $resolvedContainer.attr('data-value', 'Resolved');
    }

    function addResolveAlertButtons() {
        var $tables = $('table[data-udf-name$="Alerts"]'),
            $buttons = $tables.find('.resolveBtn'),
            $unresolved = $tables.find('tr[data-value-id] td:contains("Unresolved")');
        $buttons.remove();
        $unresolved.next().append(resolveButtonMarkup);
        $tables.find('.resolveBtn').on('click', markTargetAsResolved);
    }

    function formatField (field) {
        var $field = $(field);
        if ($field.attr('data-date-display-format')) {
            var displayFormat = $field.attr('data-date-display-format'),
                valueFormat = $field.attr('data-date-serialize-format'),
                date = $field.datepicker("getDate");
            return {
                display: moment(date).format(displayFormat),
                value: moment(date).format(valueFormat)
            };
        } else {
            return {
                value: $field.val(),
                display: $field.val()
            };
        }
    }

    // Wire up collection udfs
    $('a[data-udf-id]').on('click', function() {
        var id = $(this).data('udf-id'),
            selector = format('table[data-udf-id="%s"] * [data-field-name]', id),
            fields = $(selector).toArray(),
            data = _.map(fields, formatField);

        $(this).closest('table').append(udfRowTemplate({ fields: data }));
    });

    form.inEditModeProperty.filter(R.equals(true)).onValue(addResolveAlertButtons);

};
