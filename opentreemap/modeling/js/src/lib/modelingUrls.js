'use strict';

var _ = require('lodash'),
    url = require('url'),
    util = require('util'),
    F = require('modeling/lib/func.js'),
    config = require('treemap/lib/config.js');

function ModelingUrls(urls) {
    var instanceUrl = config.instance.url;

    // Create getter methods for each url.
    var result = _.mapValues(urls, F.getter);

    // Override getter methods for urls that require parameters.
    result = _.extend(result, {
        planUrl: function(planId) {
            return url.resolve(
                instanceUrl,
                util.format('modeling/plans/%d/', planId)
            );
        }
    });

    return result;
}

module.exports = ModelingUrls;
