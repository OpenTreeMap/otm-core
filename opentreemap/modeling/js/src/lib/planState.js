"use strict";

var _ = require('lodash'),
    Bacon = require('baconjs'),
    BU = require('treemap/lib/baconUtils.js');

module.exports = PlanState;

function PlanState(options) {
    var state = {},
        initialState = {
            id: null,
            revision: 0,
            owner: options.username,
            name: 'Untitled plan',
            description: '',
            is_published: false,
            scenarios: options.emptyScenarios,
            zoom_lat_lng: {}
        },
        urls = options.urls,
        detailsBus = new Bacon.Bus(),
        scenariosBus = new Bacon.Bus(),
        zoomLatLngLoadedBus = new Bacon.Bus(),
        shouldAutosaveBus = new Bacon.Bus(),
        saveResultBus = new Bacon.Bus();

    function getId() {
        return state.id;
    }

    function clearId() {
        state.id = null;
    }

    function load(planId) {
        var responseStream = BU.ajaxRequest({
            url: urls.planUrl(planId),
            dataType: 'json'
        })();

        responseStream.onValue(function (data) {
            state = data;
            if (state.owner !== options.username) {
                // Not my plan -- next save will make a copy
                clearId();
            }
            notifyStateChanged();
        });

        return responseStream;
    }

    function reset() {
        state = _.extend({}, initialState);
        notifyStateChanged();
    }

    function notifyStateChanged() {
        // Disable autosave so responders' initialization won't cause spurious autosaves
        shouldAutosaveBus.push(false);
        zoomLatLngLoadedBus.push(state.zoom_lat_lng);
        detailsBus.push(getDetails());
        scenariosBus.push(state.scenarios);
        shouldAutosaveBus.push(true);
    }

    function getDetails() {
        return getStateDetails(state);
    }

    function getDefaultDetails() {
        return getStateDetails(initialState);
    }

    function getStateDetails(state) {
        return {
            name: state.name,
            description: state.description,
            isPublished: state.is_published
        };
    }

    function setDetails(details) {
        state.name = details.name;
        state.description = details.description;
        state.is_published = details.isPublished;
        detailsBus.push(getDetails());
    }
    
    function setZoomLatLng(zoomLatLng) {
        if (_.isEqual(zoomLatLng, state.zoom_lat_lng)) {
            return false;
        } else {
            state.zoom_lat_lng = zoomLatLng;
            return true;
        }
    }

    var SAVE_IDLE = 0,
        SAVE_POSTED = 1,
        SAVE_NEEDED = 2,
        state_of_saves = SAVE_IDLE;

    function save(scenarios, forceUpdate) {
        // Don't post a save while another posted save is pending
        // (otherwise you would post the wrong revision number)
        if (state_of_saves === SAVE_IDLE) {
            request_save();
        } else if (state_of_saves === SAVE_POSTED) {
            state_of_saves = SAVE_NEEDED;
        }

        function request_save() {
            state.scenarios = scenarios;

            var request = createInsertOrUpdateRequest(state.id, forceUpdate),
                responseStream = request(JSON.stringify(state));

            state_of_saves = SAVE_POSTED;

            responseStream.onValue(function (data) {
                if (data.id) {
                    state.id = data.id;
                    state.revision = data.revision;
                }
                if (state_of_saves === SAVE_NEEDED) {
                    request_save();
                } else {
                    state_of_saves = SAVE_IDLE;
                    saveResultBus.push(data);
                }
            });

            responseStream.onError(function (error) {
                state_of_saves = SAVE_IDLE;
                saveResultBus.error(error);
            });

            return responseStream;
        }
    }

    function createInsertOrUpdateRequest(planId, forceUpdate) {
        if (planId && planId > 0) {
            return BU.ajaxRequest({
                url: urls.planUrl(planId) + (forceUpdate ? '?force=1' : ''),
                method: 'PUT',
                dataType: 'json'
            });
        } else {
            return BU.ajaxRequest({
                url: urls.addPlanUrl(),
                method: 'POST',
                dataType: 'json'
            });
        }
    }

    return {
        getId: getId,
        clearId: clearId,
        load: load,
        reset: reset,
        getDetails: getDetails,
        getDefaultDetails: getDefaultDetails,
        setDetails: setDetails,
        setZoomLatLng: setZoomLatLng,
        save: save,
        detailsStream: detailsBus.map(_.identity),
        scenariosStream: scenariosBus.map(_.identity),
        zoomLatLngLoadedStream: zoomLatLngLoadedBus.map(_.identity),
        shouldAutosaveProperty: shouldAutosaveBus.toProperty(),
        saveResultStream: saveResultBus.map(_.identity)
    };
}

