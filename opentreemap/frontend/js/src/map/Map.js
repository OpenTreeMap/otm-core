import React, { Component, useEffect } from 'react';
import L from 'leaflet';
import { Container, Col, Row } from 'react-bootstrap';
import { LayersControl, LayerGroup, MapContainer, TileLayer, ImageOverlay, Marker, Overlay, Popup, useMapEvents, useMap, WMSTileLayer } from "react-leaflet";
import { ImageMapLayer, BasemapLayer, TiledMapLayer } from 'react-esri-leaflet';
import ReactLeafletGoogleLayer from 'react-leaflet-google-layer';
import { BingLayer } from '../util/bing/Bing';
import { createSignature } from '../common/util/ApiRequest';
import axios from 'axios';
import config from 'treemap/lib/config';
import { BoundaryTileLayer } from './Layers';
import { PlotUtfTileLayer } from './Layers';
import { TreePopup } from './TreePopup';
import { VectorTileLayer } from '../common/util/VectorTileLayer';

//import VectorGridDefault from 'react-leaflet-vectorgrid';
//const VectorGrid = withLeaflet(VectorGridDefault);

import 'leaflet/dist/leaflet.css';
import './Map.css';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

// the below is a bugfix found in the following
// https://stackoverflow.com/questions/49441600/react-leaflet-marker-files-not-found
// https://github.com/Leaflet/Leaflet/issues/4968
let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow
});

L.Marker.prototype.options.icon = DefaultIcon;



export default class Map extends Component {
    constructor(props) {
        super(props);
        this.mapRef = React.createRef();
        this.state = {
            startingLatitude: window.django.instance_center_y,
            startingLongitude: window.django.instance_center_x,
            loading: false
        }
    }

    /*
    <VectorTileLayer
        attribution='<a href="https://new.opengreenmap.org/browse/teams/601b4587b2de180100a4db38" target="_blank">&copy; Sustainable JC<\/a>'
        url="https://new.opengreenmap.org/api-v1/tiles/{z}/{x}/{y}?format=vt&map=601b463024942b0100cc57b3"
    />
    */

    render() {
        const {loading, startingLongitude, startingLatitude, popupInfo, mapRef} = this.state;
        const { popup, setMap } = this.props;

        if (loading) return (<div>Loading...</div>);

        //attribution="https://new.opengreenmap.org/api-v1/tile/about.json?map=601b463024942b0100cc57b3&authorization=01d95994-8c91-22fc-5834-ccbbe5dbab9a"
        const locateOptions = {
            position: 'topleft',
            strings: {
                title: "Show me where I am"
            },
            onActivate: () => {}
        };

        const onLocationFound = (e) => {
            mapRef.flyTo(e.latlng, mapRef.getZoom());
        }

        if (mapRef != null) {
            mapRef.on('locationfound', onLocationFound)
        }

        const googleKey = window.django.googleApiKey;
        const bingKey = window.django.bingApiKey;

        return (
        <>
            <MapContainer
                className="map"
                center={[startingLatitude, startingLongitude]}
                zoom={13}
                whenCreated={setMap}
                scrollWheelZoom={true} >
                <LayersControl position='topright'>
                    <LayersControl.BaseLayer checked name='OpenStreetMap'>
                        <TileLayer
                            attribution='&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                        />
                    </LayersControl.BaseLayer>
                    <LayersControl.BaseLayer name='Google Hybrid'>
                        <ReactLeafletGoogleLayer
                            apiKey={googleKey}
                            type={'hybrid'}
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                        />
                    </LayersControl.BaseLayer>
                    <LayersControl.BaseLayer name='Google Streets'>
                        <ReactLeafletGoogleLayer
                            apiKey={googleKey}
                            type={'roadmap'}
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                        />
                    </LayersControl.BaseLayer>
                    <LayersControl.BaseLayer name='Esri Hybrid'>
                        <LayerGroup>
                        <BasemapLayer
                            name="Imagery"
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                        />
                        <BasemapLayer
                            name="ImageryTransportation"
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                        />
                        </LayerGroup>
                    </LayersControl.BaseLayer>
                    <LayersControl.BaseLayer name='Bing Hybrid'>
                        <BingLayer
                            maxNativeZoom={19}
                            maxZoom={25}
                            zIndex={1}
                            bingkey={bingKey}
                            type="AerialWithLabels"
                        />
                    </LayersControl.BaseLayer>
                </LayersControl>
                <LayersControl position='topright' autoZIndex={false}>
                    <LayersControl.Overlay name='Wards'>
                        <BoundaryTileLayer tilerArgs={{'category': 'Ward'}} layerOptions={{'category': 'Ward'}}/>
                    </LayersControl.Overlay>
                    <LayersControl.Overlay name='Main Neighborhoods'>
                        <BoundaryTileLayer tilerArgs={{'category': 'Main Neighborhood'}} layerOptions={{'category': 'Main Neighborhood'}}/>
                    </LayersControl.Overlay>
                    <LayersControl.Overlay name='Neighborhoods'>
                        <BoundaryTileLayer tilerArgs={{'category': 'Neighborhood'}} layerOptions={{'category': 'Neighborhood'}}/>
                    </LayersControl.Overlay>
                    <LayersControl.Overlay name='Parks'>
                        <BoundaryTileLayer tilerArgs={{'category': 'Park'}} layerOptions={{'category': 'Park'}}/>
                    </LayersControl.Overlay>
                    <LayersControl.Overlay name='SIDs'>
                        <BoundaryTileLayer tilerArgs={{'category': 'SID'}} layerOptions={{'category': 'SID'}}/>
                    </LayersControl.Overlay>
                </LayersControl>
                <PlotUtfTileLayer eventHandlers={this.props.utfEventHandlers} />
                {this.props.children}
                {popup}
            </MapContainer>
        </>
        );
    }
}

function MapClickContainer(props) {
    const map = useMapEvents({
        click: props.onClick
    });
    return null;
}

function LocateControl(props) {
    const map = useMap();

    const onLocationFound = (e) => {
        map.flyTo(e.latlng, map.getZoom());
    }

    useEffect(() => {
        if (map != null) {
            map.on('locationfound', onLocationFound)
        }
    }, [map]);

    return (
        <div className="leaflet-top leaflet-left">
            <div className="leaflet-bar leaflet-control visible-xs-block d-block d-sm-none">
                <a className="leaflet-bar-part leaflet-bar-part-single"
                    title="Show me where I am"
                    onClick={() => map.locate()} >
                    <span className="icon icon-location"></span>
                </a>
            </div>
        </div>);
}
