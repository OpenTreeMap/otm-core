"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    Bacon = require('baconjs'),
    toastr = require('toastr'),
    BU = require('treemap/lib/baconUtils.js'),
    U = require('treemap/lib/utility.js'),
    buttonEnabler = require('treemap/lib/buttonEnabler.js'),
    errors = require('manage_treemap/lib/errors.js'),
    simpleEditForm = require('treemap/lib/simpleEditForm.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    Chart = require('Chart'),
    reverse = require('reverse');

var dom = {
    selects: 'select[data-name]',
    radios: ':radio:checked[data-name]',
    roleIds: '[data-roles]',
    createNewRole: '#create_new_role',
    newRoleName: '#new_role_name',
    roles: '#role-info',
    edit: '.editBtn',
    save: '.saveBtn',
    cancel: '.cancelBtn',
    addRole: '.addRoleBtn',
    addRoleModal: '#add-role-modal',
    spinner: '.spinner',
    rolesTableContainer: '#role-info .role-table-scroll',
    newFieldsAlert: '#new-fields-alert',
    newFieldsDismiss: '#new-fields-dismiss',
    chart: '#group-chart canvas',
    treesByNeighborhoodChart: '#trees-by-neighborhood-chart canvas',
    treesByWardChart: '#trees-by-ward-chart canvas',
    speciesChart: '#species-chart canvas',
    treeConditionsByNeighborhoodChart: '#tree-conditions-by-neighborhood-chart canvas',
    treeConditionsByWardChart: '#tree-conditions-by-ward-chart canvas',
    treeDiametersChart: '#tree-diameters-chart canvas',
    ecobenefitsByWardTableHeader: '#ecobenefits-by-ward-table thead',
    ecobenefitsByWardTableBody: '#ecobenefits-by-ward-table tbody'
};

var url = reverse.roles_endpoint(config.instance.url_name),
    treesByNeighborhoodStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'count', 'neighborhood')
    )(),
    treesByWardStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'count', 'ward')
    )(),
    speciesStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'species', 'none')
    )(),
    treeConditionsByNeighborhoodStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'condition', 'neighborhood')
    )(),
    treeConditionsByWardStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'condition', 'ward')
    )(),
    ecobenefitsByWardStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'ecobenefits', 'ward')
    )(),
    treeDiametersStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'diameter', 'none')
    )();

function showError(resp) {
    enableSave();
    toastr.error(resp.responseText);
}

var chartColors = {
	red: 'rgb(255, 99, 132)',
	orange: 'rgb(255, 159, 64)',
	yellow: 'rgb(255, 205, 86)',
	green: 'rgb(75, 192, 192)',
	blue: 'rgb(54, 162, 235)',
	purple: 'rgb(153, 102, 255)',
	grey: 'rgb(201, 203, 207)',
	black: 'rgb(0, 0, 0)'
};

// theme from https://learnui.design/tools/data-color-picker.html
// starting with #add142, which is the lime-green success color in
// _base.scss
var otmGreen = '#8baa3d';
var otmLimeGreen = '#add142';
var chartColorTheme = [
    '#ffffff',
    '#e7f0c2',
    '#cce085',
    '#add142',
    '#6cc259',
    '#16b06e',
    '#009b7e',
    '#008484',
    '#006d81',
    '#005673',
    '#003f5c',
];

treesByNeighborhoodStream.onError(showError);
treesByNeighborhoodStream.onValue(function (results) {
    var chart = new Chart($(dom.treesByNeighborhoodChart), {
        type: 'bar',
        data: {
            labels: results['data'].map(x => x['name']),
            datasets: [{
                borderColor: otmLimeGreen,
                backgroundColor: otmGreen,
                data: results['data'].map(x => x['count'])
            }]
        },
    });
});

treesByWardStream.onError(showError);
treesByWardStream.onValue(function (results) {
    var chart = new Chart($(dom.treesByWardChart), {
        type: 'bar',
        data: {
            labels: results['data'].map(x => x['name']),
            datasets: [{
                borderColor: otmLimeGreen,
                backgroundColor: otmGreen,
                data: results['data'].map(x => x['count'])
            }]
        },
    });
});

speciesStream.onError(showError);
speciesStream.onValue(function (results) {
    var data = results['data'];
    var chart = new Chart($(dom.speciesChart), {
        type: 'pie',
        data: {
            labels: data.map(x => x['name']),
            datasets: [{
                data: data.map(x => x['count']),
                backgroundColor: data.map((x, i) => chartColorTheme[i]),
                borderColor: 'rgba(200, 200, 200, 0.75)',
                hoverBorderColor: 'rgba(200, 200, 200, 1)',
            }]
        },
    });
});

treeConditionsByNeighborhoodStream.onError(showError);
treeConditionsByNeighborhoodStream.onValue(function (results) {
    var data = results['data'];
    var chart = new Chart($(dom.treeConditionsByNeighborhoodChart), {
        type: 'bar',
        options: {
            scales: {
                xAxes: [{
                    stacked: true,
                }],
                yAxes: [{
                    stacked: true
                }]
            }
        },
        data: {
            labels: data.map(x => x['name']),
            datasets: [
            {
                label: 'Healthy',
                data: data.map(x => x['healthy']),
                backgroundColor: otmLimeGreen
            },
            {
                label: 'Unhealthy',
                data: data.map(x => x['unhealthy']),
                backgroundColor: chartColors.red
            },
            {
                label: 'Dead',
                data: data.map(x => x['dead']),
                backgroundColor: chartColors.black
            }]
        },
    });
});

treeConditionsByWardStream.onError(showError);
treeConditionsByWardStream.onValue(function (results) {
    var data = results['data'];
    var chart = new Chart($(dom.treeConditionsByWardChart), {
        type: 'bar',
        options: {
            scales: {
                xAxes: [{
                    stacked: true,
                }],
                yAxes: [{
                    stacked: true
                }]
            }
        },
        data: {
            labels: data.map(x => x['name']),
            datasets: [
            {
                label: 'Healthy',
                data: data.map(x => x['healthy']),
                backgroundColor: otmLimeGreen
            },
            {
                label: 'Unhealthy',
                data: data.map(x => x['unhealthy']),
                backgroundColor: chartColors.red
            },
            {
                label: 'Dead',
                data: data.map(x => x['dead']),
                backgroundColor: chartColors.black
            }]
        },
    });
});

treeDiametersStream.onError(showError);
treeDiametersStream.onValue(function (results) {
    var data = results['data'];
    var colors = chartColorTheme.reverse();
    var chart = new Chart($(dom.treeDiametersChart), {
        type: 'pie',
        data: {
            labels: data.map(x => x['name']),
            datasets: [{
                data: data.map(x => x['count']),
                backgroundColor: data.map((x, i) => colors[i]),
                borderColor: 'rgba(200, 200, 200, 0.75)',
                hoverBorderColor: 'rgba(200, 200, 200, 1)',
            }]
        },
    });
});

ecobenefitsByWardStream.onError(showError);
ecobenefitsByWardStream.onValue(function (results) {
    var data = results['data'];
    var columns = data['columns'];
    var columnHtml = '<tr>' + columns.map(x => '<th>' + x + '</th>').join('') + '</tr>';
    var dataHtml = data['data'].map(row => '<tr>' + row.map((x, i) => {
        if (row[0] == 'Total') {
            return '<td><b>' + formatColumn(x, columns[i]) + '</b></td>'
        }
        return '<td>' + formatColumn(x, columns[i]) + '</td>'
    }).join('') + '</tr>').join('');

    $(dom.ecobenefitsByWardTableHeader).html(columnHtml);
    $(dom.ecobenefitsByWardTableBody).html(dataHtml);
});

function formatColumn(column, columnName) {
    if (column == null)
        return '';
    if (typeof column == 'number' && columnName.indexOf('$') != -1)
        return '$' + column.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    if (typeof column == 'number' && column < 0.00001)
        return '';
    if (typeof column == 'number')
        return column.toLocaleString(undefined, {
            maximumFractionDigits: 4
        });
    return column;
}


buttonEnabler.run();
U.modalsFocusOnFirstInputWhenShown();
$(dom.addRole).on('click', function () {
    $(dom.addRoleModal).modal('show');
});


var alertDismissStream = $(dom.newFieldsDismiss).asEventStream('click')
    .doAction('.preventDefault')
    .map(undefined)
    .flatMap(BU.jsonRequest('POST', $(dom.newFieldsDismiss).attr('href')));

alertDismissStream.onValue(function() {
    $(dom.newFieldsAlert).hide();
    $(dom.roles).find('tr.active').removeClass('active');
});

adminPage.init(Bacon.mergeAll(alertDismissStream));

