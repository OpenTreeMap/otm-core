"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    reorderFields = require('manage_treemap/lib/reorderFields.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var attrs = {
        groupHeader: 'data-header',
        fieldKey: 'data-field',
        group: 'data-group',
        cudfSortKey: 'data-sort-key',
        cudfKey: 'data-collection-udf-key',
        groupType: 'data-type'
    },

    dom = {
        container: '#mobile-configuration',

        edit: '#mobile-configuration .editBtn',
        save: '#mobile-configuration .saveBtn',
        cancel: '#mobile-configuration .cancelBtn'
    };


adminPage.init();

reorderFields.handle({
    url: reverse.set_field_configs(config.instance.url_name),
    container: dom.container,
    editButton: dom.edit,
    saveButton: dom.save,
    cancelButton: dom.cancel,
    getFieldData: getMobileFieldsData
});

function getMobileFieldsData($groups) {
    return _($groups)
        .groupBy(getGroupType)
        .mapValues(getGroupData)
        .value();
}

function getGroupType(elem) {
    return $(elem)
        .closest('[' + attrs.groupType + ']')
        .attr(attrs.groupType);
}

function getGroupData(elems) {
    return _.map(elems, function(elem) {
        var $group = $(elem),
            $header = $group.find('[' + attrs.groupHeader + ']'),
            $sortKey = $group.find('[' + attrs.cudfSortKey + ']'),
            $list = $group.find('[' + attrs.group + ']'),
            $enabledFields = reorderFields.enabledFor($group),
            $standardFields = $enabledFields.find('[' + attrs.fieldKey + ']'),
            $cudfFields = $enabledFields.find('[' + attrs.cudfKey + ']'),

            data = {
                header: $header.attr(attrs.groupHeader)
            };

        if ($list.length >= 1) {
            data.model = $list.attr(attrs.group);
            data.field_keys = $standardFields.map(function(i, e) {
                return $(e).attr(attrs.fieldKey);
            }).get();
        }
        if ($sortKey.length >= 1) {
            var sortKey = $sortKey.attr(attrs.cudfSortKey);
            if (sortKey) {
                data.sort_key = sortKey;
            }
            data.collection_udf_keys = $cudfFields.map(function(i, e) {
                return $(e).attr(attrs.cudfKey);
            }).get();
        }
        return data;
    });
}
