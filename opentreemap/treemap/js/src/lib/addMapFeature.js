"use strict";

var $ = require('jquery'),
    _ = require('lodash'),
    toastr = require('toastr'),
    FH = require('treemap/lib/fieldHelpers.js'),
    U = require('treemap/lib/utility.js'),
    Bacon = require('baconjs'),
    reverse = require('reverse'),
    streetView = require('treemap/lib/streetView.js'),
    reverseGeocodeStreamAndUpdateAddressesOnForm =
        require('treemap/lib/reverseGeocodeStreamAndUpdateAddressesOnForm.js'),
    geocoderInvokeUi = require('treemap/lib/geocoderInvokeUi.js'),
    geocoderResultsUi = require('treemap/lib/geocoderResultsUi.js'),
    enterOrClickEventStream = require('treemap/lib/baconUtils.js').enterOrClickEventStream,
    otmTypeahead = require('treemap/lib/otmTypeahead.js'),
    config = require('treemap/lib/config.js');

function init(options) {
    var mapManager = options.mapManager,
        plotMarker = options.plotMarker,
        onClose = options.onClose || $.noop,
        clearChildEditControls = options.clearEditControls || $.noop,
        sidebar = options.sidebar,
        $sidebar = $(sidebar),
        formSelector = options.formSelector,
        indexOfSetLocationStep = options.indexOfSetLocationStep,
        addFeatureRadioOptions = options.addFeatureRadioOptions,
        addFeatureUrl = reverse.add_plot(config.instance.url_name),
        onSaveBefore = options.onSaveBefore || _.identity,

        $addFeatureHeaderLink = options.$addFeatureHeaderLink,
        $exploreMapHeaderLink = options.$exploreMapHeaderLink,

        stepControls = require('treemap/lib/stepControls.js').init($sidebar),
        addressInput = sidebar + ' .form-search input',
        $addressInput = $(addressInput),
        $summaryAddress = U.$find('.summaryAddress', $sidebar),
        $geolocateButton = U.$find('.geolocate', $sidebar),
        $geocodeError = U.$find('.geocode-error', $sidebar),
        $geolocateError = U.$find('.geolocate-error', $sidebar),
        triggerSearchBus = options.triggerSearchBus,

        $form = U.$find(formSelector, $sidebar),
        editFields = formSelector + ' [data-class="edit"]',
        validationFields = options.validationFields || formSelector + ' [data-class="error"]',
        $placeMarkerMessage = U.$find('.place-marker-message', $sidebar),
        $moveMarkerMessage = U.$find('.move-marker-message', $sidebar);

    $(editFields).show();
    $form.find('[data-class="display"]').hide();  // Hide display fields

    // Handle setting initial position via geolocate button
    var geolocateStream;
    if (navigator.geolocation) {
        geolocateStream = $geolocateButton
            .asEventStream('click')
            .flatMap(geolocate);
        geolocateStream
            .filter('.coords')
            .onValue(onGeolocateSuccess);
        geolocateStream.onError(function () {
            $geolocateError.show();
        });
    } else {
        geolocateStream = Bacon.never();
        $geolocateButton.prop('disabled', true);
    }

    // Handle user dragging the marker
    var markerFirstMoveStream = plotMarker.firstMoveStream.filter(options.inMyMode);
    markerFirstMoveStream.onValue(onMarkerMoved);

    // Handle user adding a feature
    var addFeatureStream = stepControls.allDoneStream;
    addFeatureStream.onValue(addFeature);

    // Handle user clicking "Cancel"
    var cancelStream = U.$find('.cancelBtn', $sidebar).asEventStream('click');
    cancelStream.onValue(onClose);

    // Handle internal and external deactivation
    var deactivateBus = new Bacon.Bus();
    deactivateBus.plug(cancelStream);
    deactivateBus.onValue(function () {
        // Hide/deactivate/clear everything
        plotMarker.hide();
        clearEditControls();
    });

    // Handle setting initial position via address search
    var searchTriggerStream = enterOrClickEventStream({
            inputs: addressInput,
            button: '.geocode'
        }),
        geocodeResponseStream = geocoderInvokeUi({
            searchTriggerStream: searchTriggerStream,
            addressInput: addressInput
        }),
        cleanupLocationFeedbackStream = Bacon.mergeAll([
            searchTriggerStream,
            geolocateStream,
            markerFirstMoveStream,
            addFeatureStream,
            deactivateBus
        ]),
        geocodedLocationStream = geocoderResultsUi({
            geocodeResponseStream: geocodeResponseStream,
            cancelGeocodeSuggestionStream: cleanupLocationFeedbackStream,
            resultTemplate: '#geocode-results-template',
            addressInput: addressInput,
            displayedResults: '.wrapper > .popover [data-class="geocode-result"]'
        });

    var addressTypeahead = otmTypeahead.create({
        input: addressInput,
        geocoder: true,
        geocoderBbox: config.instance.extent
    });

    cleanupLocationFeedbackStream.onValue(function hideLocationErrors() {
        $geocodeError.hide();
        $geolocateError.hide();
    });
    geocodedLocationStream.onValue(onLocationChosen);
    geocodeResponseStream.onError(function () {
        $geocodeError.show();
    });

    var markerMoveStream = plotMarker.moveStream.filter(options.inMyMode);
    var reverseGeocodeStream =
            reverseGeocodeStreamAndUpdateAddressesOnForm(markerMoveStream, formSelector);

    reverseGeocodeStream.onValue(function (response) {
        var a = response.address,
            street = a.Address,
            rest = a.City + ' ' + a.Region + ' ' + a.Postal;
        $addressInput.val(street + ' ' + rest);
        $summaryAddress.html(street + '<br/>' + rest);
    });
    reverseGeocodeStream.onError($addressInput, 'val', '');

    if (config.instance.basemap.type === 'google') {
        var $streetViewContainer = $("#streetview");
        var container = null;

        markerMoveStream.onValue(function(latlng) {
            $streetViewContainer.show();
            if (!container) {
                container = streetView.create({
                    streetViewElem: $streetViewContainer[0],
                    noStreetViewText: config.trans.noStreetViewText,
                    location: latlng,
                    hideAddress: true
                });
            }

            container.update(latlng);
        });

        deactivateBus.onValue(function () {
            $streetViewContainer.hide();
        });
    }

    // Adding a feature uses a state machine with these states and transitions:
    //
    // Inactive:
    //     activate() -> CanPlaceMarker
    //
    // CanPlaceMarker:
    //     onLocationChosen() -> CanMoveMarker
    //     cancel() -> Inactive
    //     deactivate() -> Inactive
    //
    // CanMoveMarker:
    //     onMarkerMoved() -> CanAddFeature
    //     cancel() -> Inactive
    //     deactivate() -> Inactive
    //
    // CanAddFeature:
    //     onAddFeatureSuccess() -> Inactive
    //     cancel() -> Inactive
    //     deactivate() -> Inactive

    function activate() {
        $addFeatureHeaderLink.addClass("active");
        $exploreMapHeaderLink.removeClass("active");
        plotMarker.hide();
        stepControls.showStep(0);
        stepControls.enableNext(indexOfSetLocationStep, false);
        $placeMarkerMessage.show();
        $moveMarkerMessage.hide();
    }

    function setAddFeatureUrl(url) {
        addFeatureUrl = url;
    }

    function geolocate() {
        var options = {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        };
        var deferred = $.Deferred();
        navigator.geolocation.getCurrentPosition(deferred.resolve, deferred.reject, options);
        return Bacon.fromPromise(deferred.promise());
    }

    function onGeolocateSuccess(lonLat) {
        var location = U.lonLatToWebMercator(lonLat.coords.longitude, lonLat.coords.latitude);
        onLocationChosen(location);
    }

    function onLocationChosen(location) {
        // User has chosen an initial location via geocode or geolocate.
        // Show the marker (zoomed and centered), and let them drag it.
        // Show a message so they know the marker must be moved to continue.
        mapManager.setCenterWM(location);
        plotMarker.place(location);
        requireMarkerDrag();
    }

    function requireMarkerDrag() {
        stepControls.enableNext(indexOfSetLocationStep, false);
        plotMarker.enableMoving();
        $placeMarkerMessage.hide();
        $moveMarkerMessage.show();
    }

    function onMarkerMoved() {
        // User moved marker for the first time (or clicked the map). Let them edit fields.
        stepControls.enableNext(indexOfSetLocationStep, true);
        $placeMarkerMessage.hide();
        $moveMarkerMessage.hide();
    }

    function addFeature() {
        // User hit "Done".
        $(validationFields).hide();
        var data = getFormData();
        data['plot.geom'] = plotMarker.getLocation();
        // Exclude null fields to allow defaults to be set by the server
        // If all tree fields are null, this will cause a plot w/o tree to be added
        _.each(data, function(value, key) {
            if (value === null) {
                delete data[key];
            }
        });

        $.ajax({
            url: addFeatureUrl,
            type: 'POST',
            contentType: "application/json",
            data: JSON.stringify(data),
            success: [onAddFeatureSuccess, triggerSearchBus.push],
            error: onAddFeatureError
        });
    }

    function getFormData() {
        var formData = FH.formToDictionary($form, $(editFields));
        onSaveBefore(formData);
        return formData;
    }

    function close() {
        deactivateBus.push();
        onClose();
    }

    function onAddFeatureSuccess(result) {
        // Feature was saved. Update map if appropriate.
        mapManager.updateRevHashes(result);
        var option = U.$find('input[name="' + addFeatureRadioOptions + '"]:checked', $sidebar).val();

        if (!result.enabled) {
            close();
            $('[data-feature="add_plot"]').hide();
            return;
        }

        switch (option) {
        case 'copy':
            stepControls.showStep(0);
            break;
        case 'new':
            clearEditControls();
            stepControls.showStep(0);
            break;
        case 'edit':
            close();
            var url = reverse.map_feature_detail_edit({
                instance_url_name: config.instance.url_name,
                feature_id: result.featureId,
                edit: 'edit'
            });
            window.location.hash = '';
            window.location.href = url;
            break;
        case 'close':
            close();
            break;
        }
    }

    function clearEditControls() {
        clearChildEditControls();

        addressTypeahead.clear();
        $(editFields).find('input,select').each(function () {
            var $control = $(this),
                type = $control.prop('type');
            if (type === 'checkbox' || type === 'radio') {
                $control.prop('checked', false);
            } else {
                $control.val("");
            }
        });
    }

    function onAddFeatureError(jqXHR, textStatus, errorThrown) {
        // Feature wasn't saved. Show validation errors.
        if (jqXHR.responseJSON) {
            var errorDict = jqXHR.responseJSON.fieldErrors;
            var errorSteps = _.map(errorDict, function (errorList, fieldName) {
                var errorElem = FH.getField($(validationFields), fieldName);
                if (errorElem.length > 0) {
                    errorElem.html(errorList.join(',')).show();

                    return stepControls.getStepNumberForElement(errorElem[0]);
                } else {
                    // If we can't find the step number, max - 1 is
                    // a reasonable default
                    return stepControls.maxStepNumber - 1;
                }
            });
            // Show the first step that had an error
            stepControls.showStep(_.min(errorSteps));
        } else {
            toastr.error('Failed to add feature');
            stepControls.enableNext(stepControls.maxStepNumber, true);
        }
    }

    function deactivate() {
        $addFeatureHeaderLink.removeClass("active");
        $exploreMapHeaderLink.addClass("active");

        // We're being deactivated by an external event
        deactivateBus.push();
    }

    return {
        activate: activate,
        deactivate: deactivate,
        setAddFeatureUrl: setAddFeatureUrl,
        getFormData: getFormData,
        requireMarkerDrag: requireMarkerDrag,
        stepControls: stepControls,
        addFeatureStream: addFeatureStream,
        deactivateStream: deactivateBus.map(_.identity)
    };
}

module.exports = {
    init: init
};
