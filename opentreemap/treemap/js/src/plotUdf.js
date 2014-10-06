"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    R = require('ramda'),
    moment = require('moment');

// Placed onto the jquery object
require('bootstrap-datepicker');

exports.init = function(form) {

    var udfRowTemplate = _.template(
        '<tr data-value-id="">' +
            '<% _.each(fields, function (field) { %>' +
            '<td data-value="<%= field.value %>"> <%= field.display %> </td>' +
            '<% }) %>' +
            '<td></td>' +
            '</tr>');

    // Wire up collection udfs
    $('a[data-udf-id]').click(function() {
        var id = $(this).data('udf-id');
        var fields = $('table[data-udf-id="' + id + '"] * [data-field-name]').toArray();

        var data = _.map(fields, function(field) {
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
        });

        $(this).closest('table').append(udfRowTemplate({
            fields: data
        }));
    });

    form.inEditModeProperty.filter(R.eq(true)).onValue(addResolveAlertButtons);

    function addResolveAlertButtons() {
        var $tables = $('table[data-udf-name$="Alerts"]'),
            $buttons = $tables.find('.resolveBtn'),
            $unresolved = $tables.find('tr[data-value-id] td:contains("Unresolved")');
        $buttons.remove();
        $unresolved.next().append(
            '<a href="javascript:;" class="btn btn-mini resolveBtn" data-class="edit">Resolve</a>');
        $tables.find('.resolveBtn').click(function () {
            $(this).closest('tr')
                .find('td:contains("Unresolved")')
                .attr('data-value', 'Resolved')
                .text('Resolved');
        });
    }

};
