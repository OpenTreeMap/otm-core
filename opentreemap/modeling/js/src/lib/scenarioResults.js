"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    sanitize = require('sanitize-filename'),
    U = require('treemap/lib/utility.js'),
    template = require('modeling/lib/template.js'),
    Chart = require('Chart');

var dom = {
    ecoContainer: '#scenarioResults .total-eco',
    chartContainer: '.js-charts',
    chartsHeader: '.charts-header',
    chartChooser: '.js-charts select',
    showAsCurrency: '#showAsCurrency',
    swatchPerYear: '.swatch.per-year',
    swatchCumulative: '.swatch.cumulative',
    ecoChart: '#eco-chart canvas',
    treeChart: '#tree-chart canvas',
    ecoChartLabelText: '#eco-chart .inner',
    exportGrowth: '.export-growth',
    exportEco: '.export-eco'
};

var templates = {
    ecoHeader: '#eco-header-tmpl',
    ecoFooter: '#eco-footer-tmpl',
    ecoResults: '#eco-results-tmpl'
};

var strings = window.modelingOptions.strings;

var PRIMARY_BAR_COLORS = {
        backgroundColor: "rgba(151,187,205,0.5)",
        borderColor: "rgba(151,187,205,0.8)",
        hoverBackgroundColor: "rgba(151,187,205,0.75)",
        hoverBorderColor: "rgba(151,187,205,1)"
    },
    SECONDARY_BAR_COLORS = {
        backgroundColor: "rgba(220,220,220,0.5)",
        borderColor: "rgba(220,220,220,0.8)",
        hoverBackgroundColor: "rgba(220,220,220,0.75)",
        hoverBorderColor: "rgba(220,220,220,1)"
    };

var globalChartOptions = {
    // Prevent unexpected resize behavior during initialization.
    maintainAspectRatio: false,
    animation: false,
    scales: {
        xAxes: [{
            barPercentage: 1,
            categoryPercentage: 1,
            scaleLabel: {
                display: true,
                fontSize: 14,
                labelString: strings.YEARS_SINCE_PLANTING
            },
            ticks: {
                maxRotation: 0
            }
        }],
        yAxes: [{
            scaleLabel: {
                display: true,
                fontSize: 14
            },
            ticks: {
                callback: function(value) {
                    return value.toLocaleString();
                }
            }
        }]
    },
    tooltips: {
        // Allow tooltip to include data from all datasets.
        mode: 'x-axis',
        callbacks: {
            title: function(tooltipItems, data) {
                var index = tooltipItems[0].index,
                    label = data.labels[index];
                return strings.YEAR + ' ' + label;
            },
            label: function(tooltipItem, data) {
                var dataset = data.datasets[tooltipItem.datasetIndex],
                    label = dataset.label,
                    value = dataset.data[tooltipItem.index];
                return label + ': ' + Math.round(value).toLocaleString();
            }
        }
    }
};

var initialized = false,
    ecoChart,
    treeChart;

module.exports = {
    clear: clear,
    show: show
};

function clear() {
    $(dom.ecoContainer).empty();
    if (treeChart) {
        treeChart.clear();
        treeChart.destroy();
    }
    clearEcoChart();
}

function clearEcoChart() {
    if (ecoChart) {
        ecoChart.clear();
        ecoChart.destroy(); // https://github.com/nnnick/Chart.js/issues/920
    }
}

function show(scenarioName, results) {
    var $chartChooser = $(dom.chartChooser),
        $showAsCurrency = $(dom.showAsCurrency),
        $exportGrowth = $(dom.exportGrowth),
        $exportEco = $(dom.exportEco);
    if (initialized) {
        $chartChooser.off('change');
        $showAsCurrency.off('change');
        $exportGrowth.off('click');
        $exportEco.off('click');
    } else {
        init($chartChooser, results);
    }
    $chartChooser.on('change', showTheEcoChart);
    $showAsCurrency.on('change', showTheEcoChart);
    $exportGrowth.on('click', _.partial(exportGrowth, scenarioName, results));
    $exportEco.on('click', _.partial(exportEco, scenarioName, results));

    showSummary(results);
    showTheEcoChart();
    showTreeChart(results);

    function showTheEcoChart() {
        showEcoChart(results);
    }
}

function init($chartChooser, results) {
    _.each(results.yearly_eco, function (benefit) {
        $chartChooser.append('<option>' + benefit.label + '</option>');
    });

    $(dom.swatchPerYear).css('background-color', PRIMARY_BAR_COLORS.fillColor);
    $(dom.swatchCumulative).css('background-color', SECONDARY_BAR_COLORS.fillColor);

    initialized = true;
}

function showSummary(results) {
    var $container = $(dom.ecoContainer),
        totalCurrency = 0;
    $container.append(
        template.render(templates.ecoHeader, {years: results.years}));

    _.each(results.total_eco, function (benefit) {
        // Convert e.g. "lbs/year" -> "lbs"
        var slashPos = benefit.unit.indexOf('/'),
            unit = (slashPos === -1 ? benefit.unit : benefit.unit.substr(0, slashPos));
        totalCurrency += Math.floor(benefit.currency);
        $container.append(template.render(templates.ecoResults, {
            label: benefit.label,
            currency: benefit.currency_saved,
            value: '' + benefit.value + ' ' + unit
        }));
    });

    var totalCurrencyFormatted = results.currency_symbol + totalCurrency.toLocaleString();
    $container.append(
        template.render(templates.ecoFooter, {total: totalCurrencyFormatted}));
}

function showEcoChart(results) {
    clearEcoChart();
    var index = $(dom.chartChooser)[0].selectedIndex,
        benefit = results.yearly_eco[index],
        showAsCurrency = $(dom.showAsCurrency)[0].checked,
        values = showAsCurrency ? benefit.currencies : benefit.values,
        yLabel = showAsCurrency ? results.currency_axis_label : benefit.unit,
        cumulative = [0];

    for (var i = 1; i < values.length; i++) {
        cumulative[i] = cumulative[i - 1] + values[i - 1];
    }

    var data = {
            labels: xAxisLabels(1, results.years),
            datasets: [
                _.extend({
                    data: values,
                    label: benefit.label
                }, PRIMARY_BAR_COLORS),
                _.extend({
                    data: cumulative,
                    label: strings.CUMULATIVE
                }, SECONDARY_BAR_COLORS)
            ]
        },
        options = _.merge({
            scales: {
                xAxes: [{
                    stacked: true,
                    ticks: {
                        callback: function(value, i) {
                            // Display Year 1, 5, 10, etc.
                            return i === 0 || (i + 1) % 5 === 0 ? value : '';
                        }
                    }
                }],
                yAxes: [{
                    scaleLabel: {
                        labelString: yLabel
                    }
                }]
            }
        }, globalChartOptions),
        context = setUpChart(dom.ecoChart);

    ecoChart = new Chart(context, {
        type: 'bar',
        data: data,
        options: options
    });
}

function showTreeChart(results) {
    var data = {
            labels: xAxisLabels(0, results.years),
            datasets: [
                _.extend({
                    data: results.yearly_counts,
                    label: strings.TREE_COUNTS
                }, PRIMARY_BAR_COLORS)
            ]
        },
        options = _.merge({
            scales: {
                xAxes: [{
                    ticks: {
                        callback: function(value, i) {
                            // Display Year 0, 5, 10, etc.
                            return i === 0 || i % 5 === 0 ? value : '';
                        }
                    }
                }],
                yAxes: [{
                    scaleLabel: {
                        labelString: strings.TREE_COUNTS
                    }
                }]
            }
        }, globalChartOptions),
        context = setUpChart(dom.treeChart);

    treeChart = new Chart(context, {
        type: 'bar',
        data: data,
        options: options
    });
}

function setUpChart(canvasSelector) {
    return $(canvasSelector);
}

function xAxisLabels(start, end) {
    return _.range(start, end + 1);
}

function exportGrowth(scenarioName, results) {
    var filename = sanitize(scenarioName) + ' - Growth.csv';
    U.exportToCsv(results.growth_csv_data, filename);
}

function exportEco(scenarioName, results) {
    var rows = [results.eco_csv_header],
        nBenefits = results.total_eco.length,
        y, t, label, row;
    for (var i = 0; i < nBenefits; i++) {
        y = results.yearly_eco[i];
        t = results.total_eco[i];
        label = y.label + ' (' + y.unit + ')';
        row = [label, t.value].concat(y.values);
        rows.push(row);
    }
    for (i = 0; i < nBenefits; i++) {
        y = results.yearly_eco[i];
        t = results.total_eco[i];
        label = y.label + ' (' + results.currency_axis_label + ')';
        row = [label, Math.round(t.currency)].concat(y.currencies);
        rows.push(row);
    }
    U.exportToCsv(rows, sanitize(scenarioName) + ' - Eco.csv');
}
