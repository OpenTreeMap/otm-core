var OL = require('UnpatchedOpenLayers');

// Lifted from
// https://github.com/openlayers/openlayers/blob/master/lib/OpenLayers/Request.js
//
// CORS and OpenLayers don't mix when serving behind CloudFront
//
// OpenLayers always adds in an 'x-requested-with' header (so that the
// server knows it's an XHR?). Since it is a custom header it requires a
// CORS preflight OPTIONS request.
//
// CloudFront does not support OPTIONS request so we get back an error message
//
// To make this work, we override OpenLayer's 'issue request' function
// to NOT add the X-Requested-With header, thus allowing simple CORS via
// the GET request
//
// Since we always want this hotfix to be applied it aliases the 'OpenLayers'
// namespace.
OL.Request.issue = function(config) {
    // apply default config - proxy host may have changed
    var defaultConfig = OL.Util.extend(
        this.DEFAULT_CONFIG,
        {proxy: OL.ProxyHost}
    );
    config = config || {};
    config.headers = config.headers || {};
    config = OL.Util.applyDefaults(config, defaultConfig);
    config.headers = OL.Util.applyDefaults(config.headers, defaultConfig.headers);

    // create request, open, and set headers
    var request = new OL.Request.XMLHttpRequest();
    var url = OL.Util.urlAppend(config.url,
                                        OL.Util.getParameterString(config.params || {}));
    url = OL.Request.makeSameOrigin(url, config.proxy);
    request.open(
        config.method, url, config.async, config.user, config.password
    );
    for(var header in config.headers) {
        request.setRequestHeader(header, config.headers[header]);
    }

    var events = this.events;

    // we want to execute runCallbacks with "this" as the
    // execution scope
    var self = this;

    request.onreadystatechange = function() {
        if(request.readyState == OL.Request.XMLHttpRequest.DONE) {
            var proceed = events.triggerEvent(
                "complete",
                {request: request, config: config, requestUrl: url}
            );
            if(proceed !== false) {
                self.runCallbacks(
                    {request: request, config: config, requestUrl: url}
                );
            }
        }
    };

    // send request (optionally with data) and return
    // call in a timeout for asynchronous requests so the return is
    // available before readyState == 4 for cached docs
    if(config.async === false) {
        request.send(config.data);
    } else {
        window.setTimeout(function(){
            if (request.readyState !== 0) { // W3C: 0-UNSENT
                request.send(config.data);
            }
        }, 0);
    }
    return request;
};

exports = module.exports = OL;
