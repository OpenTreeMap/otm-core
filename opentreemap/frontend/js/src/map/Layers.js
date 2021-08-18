import _ from 'lodash';
import React, { useEffect, useRef, useState } from 'react';
import config from 'treemap/lib/config';
import { TileLayer, Marker, Popup } from "react-leaflet";
import TreePopup from './TreePopup';
import UtfGrid from './UtfGrid';


export function PlotTileLayer(props) {
    const { layerOptions, tilerArgs, geoRevHash } = props;
    const [noSearchUrl, setNoSearchUrl] = useState(filterableLayer('treemap_mapfeature', 'png', options, tilerArgs || {}, geoRevHash));

    const MAX_ZOOM_OPTION = {maxZoom: 21};
    // Min zoom level for detail layers
    const MIN_ZOOM_OPTION = {minZoom: 15};

    const FEATURE_LAYER_OPTION = {zIndex: 6};

    const ref = useRef(null);
    const options = _.extend(layerOptions || {}, MAX_ZOOM_OPTION, FEATURE_LAYER_OPTION);

    useEffect(() => {
        const _noSearchUrl = filterableLayer('treemap_mapfeature', 'png', options, tilerArgs || {}, geoRevHash);
        var tileLayer = ref.current;
        setNoSearchUrl(_noSearchUrl);
        tileLayer.setUrl(_noSearchUrl);
    }, [geoRevHash]);
    /*
    useEffect(() => {
        var t = ref;
    }, [ref]);
    */

    return <TileLayer url={noSearchUrl} {...options} ref={ref} />;
}


export function BoundaryTileLayer(props) {
    const { layerOptions, tilerArgs } = props;

    const MAX_ZOOM_OPTION = {maxZoom: 21};
    // Min zoom level for detail layers
    const MIN_ZOOM_OPTION = {minZoom: 15};

    const FEATURE_LAYER_OPTION = {zIndex: 7};

    const ref = useRef(null);
    const options = _.extend(layerOptions || {}, MAX_ZOOM_OPTION, FEATURE_LAYER_OPTION);
    useEffect(() => {
        var t = ref;
    }, [ref]);
    const noSearchUrl = filterableLayer('treemap_boundary', 'png', options, tilerArgs || {}, null);

    return <TileLayer url={noSearchUrl} {...options} ref={ref} />;
}


export function PlotUtfTileLayer(props) {
    const { eventHandlers, geoRevHash } = props;
    const MAX_ZOOM_OPTION = {maxZoom: 21};
    // Min zoom level for detail layers
    const MIN_ZOOM_OPTION = {minZoom: 15};
    const [showMarker, setShowMarker] = useState(false);
    const [latLng, setLatLng] = useState({ lat: null, lng: null});
    const [url, setUrl] = useState(filterableLayer('treemap_mapfeature', 'grid.json', options, {}, geoRevHash));

    const FEATURE_LAYER_OPTION = {zIndex: 6};

    const options = _.extend({resolution: 4}, MAX_ZOOM_OPTION, FEATURE_LAYER_OPTION);
    //const url = getUrlMaker('treemap_mapfeature', 'grid.json')();

    useEffect(() => {
        const url = filterableLayer('treemap_mapfeature', 'grid.json', options, {}, geoRevHash);
        setUrl(url);
    }, [geoRevHash]);

    //return (<UtfGrid url={url} eventHandlers={eventHandlers} {...options}>
    return (<UtfGrid url={url} eventHandlers={eventHandlers} {...options} />);
}


function filterableLayer(table, extension, layerOptions, tilerArgs, geoRevHash) {
    var _geoRevHash = geoRevHash ?? config.instance.geoRevHash;
    var revToUrl = getUrlMaker(table, extension, tilerArgs),
        noSearchUrl = revToUrl(_geoRevHash),
        searchBaseUrl = revToUrl(config.instance.universalRevHash);
        //layer = L.tileLayer(noSearchUrl, layerOptions);

    /*
    layer.setHashes = function(response) {
        noSearchUrl = revToUrl(response.geoRevHash);
        searchBaseUrl = revToUrl(response.universalRevHash);

        // Update tiles to reflect content changes.
        var newLayerUrl = updateBaseUrl(layer._url, searchBaseUrl);
        layer.setUrl(newLayerUrl);
    };

    layer.setFilter = function(filters) {
        var fullUrl;
        if (Search.isEmpty(filters)) {
            fullUrl = noSearchUrl;
        } else {
            var query = Search.makeQueryStringFromFilters(filters);
            var suffix = query ? '&' + query : '';
            fullUrl = searchBaseUrl + suffix;
        }
        layer.setUrl(fullUrl);
    };
    */

    //return (<TileLayer url={noSearchUrl} />);
    return noSearchUrl;
}


function getUrlMaker(table, extension, tilerArgs) {
    return function revToUrl(rev) {
        var query = {
            'instance_id': config.instance.id,
            'restrict': JSON.stringify(config.instance.mapFeatureTypes)
        };

        if (tilerArgs) {
            _.extend(query, tilerArgs);
        }

        var paramString = new URLSearchParams(query).toString();
        return `${config.tileHost || ''}/tile/${rev}/database/otm/table/${table}/`
            + `{z}/{x}/{y}.${extension}?${paramString}`;
    };
}
