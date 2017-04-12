"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    reorderFields = require('manage_treemap/lib/reorderFields.js'),
    adminPage = require('manage_treemap/lib/adminPage.js'),
    config = require('treemap/lib/config.js'),
    reverse = require('reverse');

var attrs = {
        fieldKey: 'data-field',
        group: 'data-group',
    },

    dom = {
        container: '#search-configuration',
        websiteSearch: '#website-search',

        edit: '#search-configuration .editBtn',
        save: '#search-configuration .saveBtn',
        cancel: '#search-configuration .cancelBtn'
    };

adminPage.init();

reorderFields.handle({
    url: reverse.search_config(config.instance.url_name),
    container: dom.container,
    editButton: dom.edit,
    saveButton: dom.save,
    cancelButton: dom.cancel,
    getFieldData: getSearchFieldData
});

function getSearchFieldData($groups) {
    var data = {};
    _.each($groups, function(elem) {
        var $group = $(elem),
            $groupContainer = reorderFields.groupContainer($group),
            $list = $group.find('[' + attrs.group + ']'),
            $enabledFields = reorderFields.enabledFor($group).find('[' + attrs.fieldKey + ']'),
            group = $groupContainer.is(dom.websiteSearch) ? 'search_config' : 'mobile_search_fields';

        if (_.isUndefined(data[group])) {
            data[group] = {};
        }
        data[group][$list.attr(attrs.group)] = _.map($enabledFields, function(elem) {
            return {identifier: $(elem).attr(attrs.fieldKey)};
        });
    });
    return data;
}
