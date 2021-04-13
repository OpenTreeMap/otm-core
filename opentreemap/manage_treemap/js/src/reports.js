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
    spinner: '.spinner',
    newFieldsAlert: '#new-fields-alert',
    newFieldsDismiss: '#new-fields-dismiss',
    aggregationLevelDropdown: '#select-aggregation',

    neighborhoodDropdownContainer: '#select-neighborhoods-container',
    wardDropdownContainer: '#select-wards-container',
    parkDropdownContainer: '#select-parks-container',
    sidDropdownContainer: '#select-sids-container',

    neighborhoodDropdown: '#select-neighborhoods',
    wardDropdown: '#select-wards',
    parkDropdown: '#select-parks',
    sidDropdown: '#select-sids',

    chart: '#group-chart canvas',
    treeCountsChart: '#tree-counts-chart canvas',
    speciesChart: '#species-chart canvas',
    treeConditionsChart: '#tree-conditions-chart canvas',
    treeDiametersChart: '#tree-diameters-chart canvas',

    ecobenefitsByWardTableHeader: '#ecobenefits-by-ward-table thead',
    ecobenefitsByWardTableBody: '#ecobenefits-by-ward-table tbody',
    ecobenefitsByWardTotal: '#ecobenefits-by-ward-total'
};

var charts = {
    treeCountsChart: null,
    speciesChart: null,
    treeConditionsChart: null,
    treeDiametersChart: null,

    ecobenefitsByWardTableHeader: null,
    ecobenefitsByWardTableBody: null,
    ecobenefitsByWardTotal: null
};

// a cache to hold our data
var dataCache = {
    treeCountsChart: null,
    speciesChart: null,
    treeConditionsChart: null,
    treeDiametersChart: null,
    ecobenefits: null,
};

var onValueFunctions = {
    treeCountsChart: null,
    speciesChart: null,
    treeConditionsChart: null,
    treeDiametersChart: null,
    ecobenefits: null,
}

var url = reverse.Urls.roles_endpoint(config.instance.url_name);

function loadData() {

    var aggregationLevel = $(dom.aggregationLevelDropdown).val();
    var treeCountStream = BU.jsonRequest(
        'GET',
        reverse.Urls.get_reports_data(config.instance.url_name, 'count', aggregationLevel)
    )();
    treeCountStream.onError(showError);
    treeCountStream.onValue(onValueFunctions.treeCountsChart);

    var speciesStream = BU.jsonRequest(
        'GET',
        reverse.Urls.get_reports_data(config.instance.url_name, 'species', aggregationLevel)
    )();
    speciesStream.onError(showError);
    speciesStream.onValue(onValueFunctions.speciesChart);

    var treeConditionsStream = BU.jsonRequest(
        'GET',
        reverse.Urls.get_reports_data(config.instance.url_name, 'condition', aggregationLevel)
    )();
    treeConditionsStream.onError(showError);
    treeConditionsStream.onValue(onValueFunctions.treeConditionsChart);

    var treeDiametersStream = BU.jsonRequest(
        'GET',
        reverse.Urls.get_reports_data(config.instance.url_name, 'diameter', aggregationLevel)
    )();
    treeDiametersStream.onError(showError);
    treeDiametersStream.onValue(onValueFunctions.treeDiametersChart);

    $(dom.ecobenefitsByWardTotal).html('');
    $(dom.spinner).show();
    var ecobenefitsStream = BU.jsonRequest(
        'GET',
        reverse.Urls.get_reports_data(config.instance.url_name, 'ecobenefits', aggregationLevel)
    )();
    ecobenefitsStream.onError(showError);
    ecobenefitsStream.onValue(onValueFunctions.ecobenefits);
}


function showError(resp) {
    enableSave();
    toastr.error(resp.responseText);
}

var chartColors = {
	orange: 'rgb(255, 159, 64)',
	yellow: 'rgb(255, 205, 86)',
	green: 'rgb(75, 192, 192)',
	blue: 'rgb(54, 162, 235)',
	purple: 'rgb(153, 102, 255)',
	grey: 'rgb(201, 203, 207)',

    // a less saturated red
    red: '#8b1002',

    // a softer black
    black: '#303031'
};

// theme from https://learnui.design/tools/data-color-picker.html
// starting with #8baa3d, which is the otm-green color in
// _base.scss
var otmGreen = '#8baa3d';
var otmLimeGreen = '#add142';
var chartColorTheme = [
    '#003f5c',
    '#00506b',
    '#006274',
    '#007374',
    '#00836c',
    '#1c935f',
    '#59a04e',
    '#8baa3d'
];


onValueFunctions.treeCountsChart = function (results) {
    var data = results['data']
    dataCache.treeCountsChart = data;

    if (charts.treeCountsChart == null) {
        var chart = new Chart($(dom.treeCountsChart), {
            type: 'bar',
            data: {
                labels: [],
                datasets: []
            }
        });

        charts.treeCountsChart = chart;
    }

    updateTreeCountsData(data);
};

function updateTreeCountsData(data) {
    var chart = charts.treeCountsChart;
    if (chart == null) {
        return;
    }

    chart.data.labels = data.map(x => x['name']);
    chart.data.datasets = [{
        label: 'Trees',
        borderColor: otmLimeGreen,
        backgroundColor: otmGreen,
        data: data.map(x => x['count'])
    }];
    chart.update();
}

onValueFunctions.speciesChart = function (results) {
    var data = results['data'];
    dataCache.speciesChart = data;

    updateSpeciesData(data);
}

function updateSpeciesData(data) {
    var chart = charts.speciesChart;
    if (chart != null) {
        chart.destroy();
    }

    // reduce the species and counts, as there are multiple given the aggregation
    var reduceFunc = function(acc, value) {
        acc[value['species_name']] = acc[value['species_name']] + value['count']
            || value['count'];
        return acc;
    }
    var dataObj = data.reduce(reduceFunc, {});
    // make into a list of items and sort descending
    data = Object.keys(dataObj).map(k => {return {name: k, count: dataObj[k]}})
        .sort((first, second) => second['count'] - first['count']);

    // take the first N and aggregate the rest
    var finalData = data.slice(0, 5);
    var otherSum = data.slice(5).reduce((acc, val) => acc + val['count'], 0);
    finalData.push({name: 'Other', count: otherSum})

    var chart = new Chart($(dom.speciesChart), {
        type: 'pie',
        data: {
            labels: finalData.map(x => x['name']),
            datasets: [{
                data: finalData.map(x => x['count']),
                backgroundColor: finalData.map((x, i) => chartColorTheme[i]),
                borderColor: 'rgba(200, 200, 200, 0.75)',
                hoverBorderColor: 'rgba(200, 200, 200, 1)',
            }]
        }
    });
    charts.speciesChart = chart;
    chart.update();
}

onValueFunctions.treeConditionsChart = function (results) {
    var data = results['data'];
    dataCache.treeConditionsChart = data;

    if (charts.treeConditionsChart == null) {
        var chart = new Chart($(dom.treeConditionsChart), {
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
                labels: [],
                datasets: []
            }
        });
        charts.treeConditionsChart = chart;
    }

    updateTreeConditionsChart(data);
}

function updateTreeConditionsChart(data) {
    var chart = charts.treeConditionsChart;
    if (chart == null) {
        return;
    }

    chart.data.labels = data.map(x => x['name']);
    chart.data.datasets = [
        {
            label: 'Healthy',
            data: data.map(x => x['healthy']),
            backgroundColor: otmGreen
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
        }
    ];
    chart.update();
}

onValueFunctions.treeDiametersChart = function (results) {
    var data = results['data'];
    dataCache.treeDiametersChart = data;
    updateTreeDiametersChart(data);
}

function updateTreeDiametersChart(data) {
    var chart = charts.treeDiametersChart;
    if (chart != null) {
        chart.destroy();
    }
    //
    // reduce the species and counts, as there are multiple given the aggregation
    var reduceFunc = function(acc, value) {
        var diameter = value['diameter'];
        if (diameter <= 5) {
            acc['< 5 in.'] = acc['< 5 in.'] + 1 || 1;
        } else if (diameter > 5 && diameter < 25){
            acc['> 5 in. and < 25 in.'] = acc['> 5 in. and < 25 in.'] + 1 || 1;
        } else {
            acc['> 25 in.'] = acc['> 25 in.'] + 1 || 1;
        }
        return acc;
    }
    var dataObj = data.reduce(reduceFunc, {});
    // make into a list of items and sort descending
    data = Object.keys(dataObj).map(k => {return {name: k, count: dataObj[k]}});

    var colors = chartColorTheme.reverse();
    var chart = new Chart($(dom.treeDiametersChart), {
        type: 'pie',
        data: {
            labels: data.map(x => x['name']),
            datasets: [{
                data: data.map(x => x['count']),
                backgroundColor: data.map((x, i) => colors[i * 2]),
                borderColor: 'rgba(200, 200, 200, 0.75)',
                hoverBorderColor: 'rgba(200, 200, 200, 1)',
            }]
        },
    });
    charts.treeDiametersChart = chart;
}

onValueFunctions.ecobenefits = function (results) {
    var data = results['data'];
    dataCache.ecobenefits = data;
    $(dom.spinner).hide();
    updateEcobenefits(data);
}

function updateEcobenefits(data) {
    var columns = data['columns'];
    var columnHtml = '<tr>' + columns.map(x => '<th>' + x + '</th>').join('') + '</tr>';
    var dataHtml = data['data'].map(row => '<tr>' + row.map((x, i) => {
        if (row[0] == 'Total') {
            return '<td><b>' + formatColumn(x, columns[i]) + '</b></td>';
        }
        return '<td>' + formatColumn(x, columns[i]) + '</td>';
    }).join('') + '</tr>').join('');

    $(dom.ecobenefitsByWardTableHeader).html(columnHtml);
    $(dom.ecobenefitsByWardTableBody).html(dataHtml);

    // compute the totals
    var total = data['data'].flatMap(row => row.map((x, i) => {
        if (row[0] == 'Total') {
            return 0;
        }
        if (columns[i].indexOf('$') != -1) {
            return x;
        } else {
            return 0;
        }
    })).reduce((a, b) => a + b, 0);

    $(dom.ecobenefitsByWardTotal)
        .html('<b>Total Annual Benefits: $' + total.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }) + '</b>');
}

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

$(dom.neighborhoodDropdown).change(function(event) {
    var name = $(this).val();
    filterDataByAggregation(name);
});

$(dom.wardDropdown).change(function(event) {
    var name = $(this).val();
    filterDataByAggregation(name);
});

$(dom.parkDropdown).change(function(event) {
    var name = $(this).val();
    filterDataByAggregation(name);
});

$(dom.sidDropdown).change(function(event) {
    var name = $(this).val();
    filterDataByAggregation(name);
});

function filterDataByAggregation(name) {
    var data = dataCache.treeCountsChart;

    updateTreeCountsData(
        data.filter(x => name == 'all' || name.includes(x['name']))
    );

    data = dataCache.speciesChart;
    updateSpeciesData(
        data.filter(x => name == 'all' || name.includes(x['name']))
    );

    data = dataCache.treeConditionsChart;
    updateTreeConditionsChart(
        data.filter(x => name == 'all' || name.includes(x['name']))
    );

    data = dataCache.treeDiametersChart;
    updateTreeDiametersChart(
        data.filter(x => name == 'all' || name.includes(x['name']))
    );

    data = dataCache.ecobenefits;
    updateEcobenefits({
        columns: data['columns'],
        data: data['data'].filter(x => name == 'all' || name.includes(x[0]))
    });
}

$(dom.aggregationLevelDropdown).change(function(event) {
    var aggregationLevel = $(dom.aggregationLevelDropdown).val();

    $(dom.wardDropdownContainer + " option:selected").removeAttr("selected");
    $(dom.neighborhoodDropdownContainer + " option:selected").removeAttr("selected");
    $(dom.parkDropdownContainer + " option:selected").removeAttr("selected");
    $(dom.sidDropdownContainer + " option:selected").removeAttr("selected");

    // could probably do toggle, but i'm paranoid something will break
    if (aggregationLevel == "ward") {
        $(dom.wardDropdownContainer).show();
        $(dom.wardDropdownContainer + " option[value=all]").attr("selected", true);
        $(dom.neighborhoodDropdownContainer).hide();
        $(dom.parkDropdownContainer).hide();
        $(dom.sidDropdownContainer).hide();
    } else if (aggregationLevel == "neighborhood"){
        $(dom.wardDropdownContainer).hide();
        $(dom.neighborhoodDropdownContainer).show();
        $(dom.neighborhoodDropdownContainer + " option[value=all]").attr("selected", true);
        $(dom.parkDropdownContainer).hide();
        $(dom.sidDropdownContainer).hide();
    } else if (aggregationLevel == "park"){
        $(dom.wardDropdownContainer).hide();
        $(dom.neighborhoodDropdownContainer).hide();
        $(dom.parkDropdownContainer).show();
        $(dom.parkDropdownContainer + " option[value=all]").attr("selected", true);
        $(dom.sidDropdownContainer).hide();
    } else if (aggregationLevel == "sid"){
        $(dom.wardDropdownContainer).hide();
        $(dom.neighborhoodDropdownContainer).hide();
        $(dom.parkDropdownContainer).hide();
        $(dom.sidDropdownContainer).show();
        $(dom.sidDropdownContainer + " option[value=all]").attr("selected", true);
    }

    loadData();
});


buttonEnabler.run();
U.modalsFocusOnFirstInputWhenShown();

var alertDismissStream = $(dom.newFieldsDismiss).asEventStream('click')
    .doAction('.preventDefault')
    .map(undefined)
    .flatMap(BU.jsonRequest('POST', $(dom.newFieldsDismiss).attr('href')));

alertDismissStream.onValue(function() {
    $(dom.newFieldsAlert).hide();
});

adminPage.init(Bacon.mergeAll(alertDismissStream));

// initially, show by Ward
$(dom.wardDropdownContainer).show();
$(dom.neighborhoodDropdownContainer).hide();
$(dom.parkDropdownContainer).hide();
$(dom.sidDropdownContainer).hide();
$(dom.wardDropdownContainer + " option[value=all]").attr("selected", true);
loadData();
