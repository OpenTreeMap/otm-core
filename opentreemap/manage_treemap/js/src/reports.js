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
    treeDiametersChart: '#tree-diameters-chart canvas'
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
    )();
    /*
    treeDiametersStream = BU.jsonRequest(
        'GET',
        reverse.get_reports_data(config.instance.url_name, 'diameter', '')
    )();
    */

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
	grey: 'rgb(201, 203, 207)'
};

var dynamicColors = function() {
    var r = Math.floor(Math.random() * 255);
    var g = Math.floor(Math.random() * 255);
    var b = Math.floor(Math.random() * 255);
    return "rgb(" + r + "," + g + "," + b + ")";
};

treesByNeighborhoodStream.onError(showError);
treesByNeighborhoodStream.onValue(function (results) {
    var chart = new Chart($(dom.treesByNeighborhoodChart), {
        type: 'bar',
        data: {
            labels: results['data'].map(x => x['name']),
            datasets: [{
                label: 'Trees',
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
                label: 'Trees',
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
                backgroundColor: data.map(x => dynamicColors()),
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
                backgroundColor: chartColors.green
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
                backgroundColor: chartColors.green
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


/*
treeDiametersStream.onError(showError);
treeDiametersStream.onValue(function (results) {
    var chart = new Chart($(dom.chart), {
        type: 'bar',
        data: {
            labels: results['data'].map(x => x['neighborhood']),
            datasets: [{
                label: 'Trees',
                data: results['data'].map(x => x['total'])
            }]
        },
    });
});
*/

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

//adminPage.init(Bacon.mergeAll(updateStream, alertDismissStream));

