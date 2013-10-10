"use strict";

var $ = require('jquery'),
    BU = require('BaconUtils'),
    url = require('url'),
    U = require('utility'),
    _ = require('underscore'),
    Bacon = require('baconjs');


// Given a map of logical names to jquery elements
// (such as {e1: $(...), e2: $(...)})
//
// return a new RadioGroup with a single method
// show(name) that will hide all elements except
// name
var RadioGroup = function(elementMap) {
    this.show = function(elementToShow) {
        _.each(elementMap, function($thing, name) {
            if (name === elementToShow) {
                $thing.show();
            } else {
                $thing.hide();
            }
        });
    };
};

// Used to control polling.
//
// On each polling loop `generator` is called
// and if either the result is falsey, or
// someone has called `stop`, the polling will stop.
var RepeatPredicate = function(generator) {
    var that = this;

    this._stopped = false;

    this.stop = function() { that._stopped = true; };

    this.next = function() {
        if (that._stopped) {
            return false;
        } else {
            return generator();
        }
    };
};

function getCheckUrlForJob(options, jobId) {
    return U.appendSegmentToUrl(jobId, options.checkTreeExportUrl, true);
}

function startNewPollingLoop(interval, predicate) {
    var pollStream = Bacon.fromPoll(interval, function() {
        var next = predicate.next();
        return next ? new Bacon.Next(next) : new Bacon.End();
    });

    return pollStream;
}

exports.init = function(options) {
    var initialRequestStream = $(options.trigger).asEventStream('click')
            .map(function() {
                return {q: url.parse(window.location.href, true).query.q || '' };
            })
            .flatMap(BU.jsonRequest('GET', options.startTreeExportUrl));

    var activePredicate = null;

    $(options.cancel).asEventStream('click')
        .onValue(function() {
            if (activePredicate) { activePredicate.stop(); }
        });

    var messageRadioGroup = new RadioGroup({
        prep: $(options.panel).find('.prep-msg'),
        err: $(options.panel).find('.error-msg')
    });

    var dismissRadioGroup = new RadioGroup({
        cancel: $(options.panel).find('.dismiss-cancel'),
        ok: $(options.panel).find('.dismiss-ok')
    });

    var $panel = $(options.panel);

    initialRequestStream
        .onError(function() {
            if (activePredicate) { activePredicate.stop(); }

            messageRadioGroup.show('error');
            dismissRadioGroup.show('ok');

            $panel.modal('show');
        });

    // While there is an active job id, query the
    // check exporter end-point
    var interval = 2000; // 2s

    var startNewActiveJobPollingLoop = function(pred) {
        var responseStream = startNewPollingLoop(interval, pred)
                .map(getCheckUrlForJob, options)
                .flatMap(function(url) { return BU.jsonRequest('GET', url)(); });

        responseStream.onValue(function(resp) {
            if (resp.status == 'COMPLETE') {
                // Tirgger the download
                pred.stop();

                window.location.href = resp.url;
                $panel.modal('hide');
            } else if (resp.status != 'PENDING') {
                pred.stop();

                // Error response or something we can't handle
                dismissRadioGroup.show('ok');

                $panel.find('.modal-body').html(resp.message);
            }
        });

        responseStream.onError(function() {
            pred.stop();

            dismissRadioGroup.show('ok');
            messageRadioGroup.show('error');
        });
    };

    initialRequestStream
        .map('.job_id')
        .onValue(function(jobid) {
            messageRadioGroup.show('prep');
            dismissRadioGroup.show('cancel');

            $panel.modal('show');

            if (activePredicate) {
                // Stop an existing job if it exists
                activePredicate.stop();
            }

            activePredicate = new RepeatPredicate(function() { return jobid; });
            startNewActiveJobPollingLoop(activePredicate);
        });
};
