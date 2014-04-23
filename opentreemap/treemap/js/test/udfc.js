"use strict";

var assert = require('chai').assert,
    format = require('util').format,
    $ = require('jquery'),
    Bacon = require('baconjs'),
    udfcSearch = require('treemap/udfcSearch'),
    _ = require('lodash');

require('treemap/baconUtils');

var initialDomData = {
    body: '<div class="udfc-search">' +
        '  <span>I am looking for</span>' +
        '  <select id="udfc-search-model">' +
        '    <option data-class="udfc-placeholder" selected />' +
        '    <option data-model="tree">trees</option>' +
        '    <option data-model="plot">plots</option>' +
        '  </select>' +
        '  <select id="udfc-search-type">' +
        '    <option data-class="udfc-placeholder" selected />' +
        '    <option data-type="stewardship"' +
        '            data-plot-udfd-id="18"' +
        '            data-tree-udfd-id="19"' +
        '            data-date-field-key="Date"' +
        '            data-action-field-key="Action"' +
        '            >that received</option>' +
        '    <option data-type="alerts"' +
        '            data-plot-udfd-id=""' +
        '            data-tree-udfd-id=""' +
        '            data-date-field-key="Date Noticed"' +
        '            data-action-field-key="Action Needed"' +
        '            >that need</option>' +
        '  </select>' +
        '  <div id="udfc-extra-clauses" style="display: none">' +
        '    <input id="alerts-resolved"' +
        '           data-type="alerts"' +
        '           data-field="Status"' +
        '           data-search-type="IS"' +
        '           value="Unresolved"/>' +
        '  </div>' +
        '  <select id="udfc-search-action" data-search-type="IS">' +
        '    <option data-class="udfc-placeholder" selected />' +
        '    <option data-model="tree" data-type="stewardship" style="display: none;">Watering</option>' +
        '    <option data-model="tree" data-type="stewardship" style="display: none;">Pruning</option>' +
        '    <option data-model="tree" data-type="stewardship" style="display: none;">Mulching, Adding Compost or Amending Soil</option>' +
        '    <option data-model="tree" data-type="stewardship" style="display: none;">Removing Debris or Trash</option>' +
        '    <option data-model="plot" data-type="stewardship" style="display: none;">Enlarging the Planting Area</option>' +
        '    <option data-model="plot" data-type="stewardship" style="display: none;">Adding a Guard</option>' +
        '    <option data-model="plot" data-type="stewardship" style="display: none;">Removing a Guard</option>' +
        '    <option data-model="plot" data-type="stewardship" style="display: none;">Herbaceous Planting</option>' +
        '  </select>' +
        '  <span>between</span>' +
        '  <input id="udfc-search-date-from" data-search-type="MIN"' +
        '         class="stewardship-selector"' +
        '         data-date-format="mm/dd/yyyy"' +
        '         />' +
        '  <span>and</span>' +
        '  <input id="udfc-search-date-to" data-search-type="MAX"' +
        '         class="stewardship-selector"' +
        '         data-date-format="mm/dd/yyyy"' +
        '         />' +
        '</div>',
    treeActions: {
        count: 4,
        visibleCount: 0
    },
    plotActions: {
        count: 4,
        visibleCount: 0
    }
};


var assertEqualDescriptive = function (arg1, arg2, descriptor, entity) {
    var formatString = "%s %ss on the dom, %s, to match " +
            "expected %s %ss after state change, %s";
    assert.equal(arg1, arg2,
                 format(formatString, descriptor, entity, arg1,
                        descriptor, entity, arg2));
};

var assertActionExpectations = function (expectations) {
    var $action = $(udfcSearch._widgets.action.selector),
        $options = $action.find('option'),
        $treeOptions = $options.filter('[data-model="tree"]'),
        $plotOptions = $options.filter('[data-model="plot"]');

    assertEqualDescriptive(invisible($plotOptions).length,
                           expectations.invisiblePlotOptions,
                           'invisible', 'plot action');
    assertEqualDescriptive(invisible($treeOptions).length,
                 expectations.invisibleTreeOptions,
                 'invisible', 'tree action');
    assertEqualDescriptive(visible($plotOptions).length,
                 expectations.visiblePlotOptions,
                 'visible', 'plot action');
    assertEqualDescriptive(visible($treeOptions).length,
                 expectations.visibleTreeOptions,
                 'visible', 'tree action');
    assertEqualDescriptive($action.val(),
                 expectations.actionVal,
                 '', 'actionValue');
    assertEqualDescriptive($action.attr('name'),
                           expectations.actionName,
                           '', 'actionName');
};

var emptyActionExpectations = {
    invisiblePlotOptions: initialDomData.plotActions.count,
    invisibleTreeOptions: initialDomData.treeActions.count,
    visiblePlotOptions: initialDomData.plotActions.visibleCount,
    visibleTreeOptions: initialDomData.treeActions.visibleCount,
    actionVal: '',
    actionName: ''
};

var pushStateDiffTestCases = {
    "Empty model, no name attribute, no visible actions": {
        stateDiff: {
            modelName: null
        },
        domExpectations: emptyActionExpectations
    },
    "not enough data, no name attribute, no visible actions": {
        stateDiff: {
            modelName: 'trees'
        },
        domExpectations: emptyActionExpectations
    },
    "tree stewardship, visible actions": {
        stateDiff: {
            modelName: 'tree',
            type: 'stewardship',
            treeUdfFieldDefId: '18',
            plotUdfFieldDefId: '19',
            dateFieldKey: 'data',
            actionFieldKey: 'action'
        },
        domExpectations: _.extend(
            {}, emptyActionExpectations, {
                invisibleTreeOptions: 0,
                visibleTreeOptions: initialDomData.treeActions.count,
                actionName: 'udf:tree:18.action' })
    }
};


var makeNameAttributeTestCases = {
    "missing data 1": {
        state: {modelName: 'plot'},
        fieldKey: 'actionFieldKey',
        outputs: ''
    },
    "missing data 2": {
        state: {modelName: 'plot', plotUdfFieldDefId: '18'},
        fieldKey: 'actionFieldKey',
        outputs: ''
    },
    "invalid model name produces nonexistent <modelname>UdfFieldDefId, gets no name": {
        state: {modelName: 'foo', plotUdfFieldDefId: '18', treeUdfFieldDefId: '19',
                actionFieldKey: 'Action!', dateFieldKey: "When"},
        fieldKey: 'dateFieldKey',
        outputs: ''
    },
    "valid 1": {
        state: {modelName: 'plot', plotUdfFieldDefId: '18', treeUdfFieldDefId: '19',
               actionFieldKey: 'Action', dateFieldKey: "When"},
        fieldKey: 'actionFieldKey',
        outputs: 'udf:plot:18.Action'
    },
    "valid 2": {
        state: {modelName: 'tree', plotUdfFieldDefId: '18', treeUdfFieldDefId: '19',
                actionFieldKey: 'Action!', dateFieldKey: "When"},
        fieldKey: 'dateFieldKey',
        outputs: 'udf:tree:19.When'
    }
};

module.exports = {
    'makeNameAttribute': _.mapValues(makeNameAttributeTestCases, function(testCase) {
        return function() {
            var outputs = udfcSearch._makeNameAttribute(testCase.state,
                                                        testCase.state[testCase.fieldKey]);
            assert.deepEqual(outputs, testCase.outputs, 'The elems should match');
        };
    }),
    'diff states': _.mapValues(pushStateDiffTestCases, function(testCase) {
        return function () {
            $('body').append('<div id="test-canvas" />');
            $('#test-canvas').append(initialDomData.body);

            var usearch = udfcSearch.init();
            usearch._externalChangeBus.push(testCase.stateDiff);
            assertActionExpectations(testCase.domExpectations);

            $('#test-canvas').empty();

        };
    })
};
