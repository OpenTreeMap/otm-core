import React, { Component, useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Button, Container, Col, Row } from 'react-bootstrap';
import axios from 'axios';

import L from 'leaflet';
import config from 'treemap/lib/config';
import reverse from 'reverse';
import { useMapEvents } from "react-leaflet";

import Map from './Map';
import './Map.css';
import { TreePopup } from './TreePopup';
import { Marker, Popup } from "react-leaflet";

import { PlotTileLayer } from './Layers';
import { DetailSidebar } from '../sidebar/DetailSidebar';
import { AddTreeSidebar } from '../sidebar/AddTreeSidebar';
import { Footer } from './Footer';


export default class MapMain extends Component {
    constructor(props) {
        super(props);
        this.state = {
            map: null,
            showAddTree: window.django.shouldAddTree,
            isAuthenticated: window.django.user.is_authenticated,
            addTreeMarkerInfo: {
                show: false,
                latLng: { lat: null, lng: null }
            },
            popupInfo: {
                ids: null,
                show: false,
                latLng: { lat: null, lng: null }
            },
            addSelectedMarkerInfo: {
                show: false,
                latLng: { lat: null, lng: null }
            },
            sidebarInfo: null,
            benefits: null,
            geoRevHash: config.instance.geoRevHash
        };
        this.setShowAddTree = this.setShowAddTree.bind(this);
        this.setShowEcobenefits = this.setShowEcobenefits.bind(this);
        this.onMapClick = this.onMapClick.bind(this);
        this.onUtfMapClick = this.onUtfMapClick.bind(this);
        this.getPopup = this.getPopup.bind(this);
        this.onAddMapFeature = this.onAddMapFeature.bind(this);

    }

    componentDidMount() {
        var url = `/${window.django.instance_url}/benefit/search/api`;
        axios.get(url, {withCredential: true})
            .then(res => {
                this.setState({
                    benefits: res.data
                });
                console.log(res);
            }).catch(res => {
                this.setState({
                    benefits: null
                });
                console.log(res);
            });
    }

    setShowAddTree(value) {
        this.setState({
            showAddTree: value,
            addTreeMarkerInfo: {
                show: false,
                latLng: { lat: null, lng: null }
            },
            popupInfo: {
                ids: null,
                show: false,
                latLng: { lat: null, lng: null }
            },
            addSelectedMarkerInfo: {
                show: false,
                latLng: { lat: null, lng: null }
            },
        });

        // add the feature-selected to the body for legacy css purposes
        document.body.classList.remove('feature-selected');
    }

    setShowEcobenefits(event) {
        this.setState({
            showAddTree: false,
            addTreeMarkerInfo: {
                show: false,
                latLng: { lat: null, lng: null }
            },
        });
    }

    onMapClick(e) {
        const { showAddTree } = this.state;
        if (!showAddTree) return;

        this.setState({
            addTreeMarkerInfo: {
                show: true,
                latLng: e.latlng
            },
        });
    }

    onUtfMapClick(e) {
        if (e.id == null) {
            this.setState({
                popupInfo: {
                    ids: null,
                    show: false,
                    latLng: { lat: null, lng: null }
                },
                addSelectedMarkerInfo: {
                    show: false,
                    latLng: { lat: null, lng: null }
                },
                sidebarInfo: null
            });
            // add the feature-selected to the body for legacy css purposes
            document.body.classList.remove('feature-selected');
        } else {
            this.setState({
                popupInfo: {
                    // FIXME can there be multiple?
                    ids: [e.id],
                    show: true,
                    latLng: { lat: e.latlng.lat, lng: e.latlng.lng }
                },
                addSelectedMarkerInfo: {
                    show: true,
                    latLng: { lat: e.latlng.lat, lng: e.latlng.lng }
                }
            });

            const url = reverse.Urls.map_feature_accordion_api({
                instance_url_name: window.django.instance_url,
                feature_id: e.id
            });
            axios.get(url, {withCredential: true})
                .then(res => {
                    this.setState({
                        sidebarInfo: res.data
                    });
                    console.log('success');
                    console.log(res);
                }).catch(err => {
                    this.setState({
                        sidebarInfo: null
                    });
                    console.log('error');
                    console.log(err);
                });

            // add the feature-selected to the body for legacy css purposes
            document.body.classList.add('feature-selected');
        }
    }

    onAddMapFeature = (data) => {
        this.setState({
            geoRevHash: data.geoRevHash
        });
    }

    getPopup() {
        const { showAddTree, popupInfo, addTreeMarkerInfo, addSelectedMarkerInfo } = this.state;
        if (popupInfo.show && !showAddTree) {
            const marker = addSelectedMarkerInfo.show
                ? (<ShowFeatureMarker {...addSelectedMarkerInfo} />)
                : '';

            return (<>
                <TreePopup {...popupInfo} />
                {marker}
            </>);
        }

        if (addTreeMarkerInfo.show && showAddTree) {
            return (
                <AddTreeMarker
                    latLng={addTreeMarkerInfo.latLng}
                    updateLatLng={(lat, lng) => {
                        this.setState({
                            addTreeMarkerInfo: {
                                show: true,
                                latLng: {lat: lat, lng: lng}
                            }
                        });
                    }}
                    />
            );
        }

        return null;
    }

    render() {
        const {
            benefits,
            showAddTree,
            popupInfo,
            sidebarInfo,
            map,
            addTreeMarkerInfo,
            addSelectedMarkerInfo,
            geoRevHash,
            isAuthenticated
        } = this.state;

        const utfEventHandlers = {
            click: this.onUtfMapClick
        }

        const popup = this.getPopup();

        const sideBar = showAddTree
            ? <AddTreeSidebar
                    onClose={() => this.setShowAddTree(false)}
                    latLng={addTreeMarkerInfo.latLng}
                    clearLatLng={() => this.setState({
                        addTreeMarkerInfo: {
                            show: true,
                            latLng: {lat: lat, lng: lng}
                        }})}
                    map={map}
                    onMapClick={this.onMapClick}
                    onAddMapFeature={this.onAddMapFeature}
                />
            : <DetailSidebar
                    benefits={benefits}
                    sidebarInfo={sidebarInfo}
                    map={map}
                    addSelectedMarkerInfo={addSelectedMarkerInfo}
                />;

        const plotTileLayer = (<PlotTileLayer geoRevHash={geoRevHash}/>);

        // FIXME use something less hacky for the navbar
        return (
        <>
            <div className="navbar navbar-expand fixed-top bg-dark navbar-dark"
                style={{ width: '110px', zIndex: 10000 }}>
                <ul className="navbar-nav nav mr-auto">
                    <li className="nav-item">
                        <a
                            className="nav-link"
                            onClick={() => this.setState({showAddTree: true})}>Add a Tree</a>
                    </li>
                </ul>
            </div>
            <div className={`header instance-header collapsed ${showAddTree ? "hide-search" : ""}`}>
                <div className="logo">
                    <a href="/jerseycity/map/"><img id="site-logo" src="/media/logos/logo-jerseycity-f9414dae710646a22b3ad0e7480a4fce.png" alt="OpenTreeMap"></img>
                    </a>
                </div>
                <div className="toolbar-wrapper"></div>
                <div className="search-wrapper">
                    <div className="search-block-wrapper" style={{display: 'none'}}>
                        <label>Search by Species</label>
                        <div className="autocomplete-group">
                            <input name="species.id" />
                        </div>
                    </div>
                </div>
            </div>
            <div className="subhead">
                <div className="advanced-search">Advanced Search</div>
                <div className="stats-bar">
                    <div className="stats-list">
                        <div id="tree-and-planting-site-counts">
                        <span>{benefits?.n_trees?.toLocaleString()}</span> trees, <span>{benefits?.n_empty_plots?.toLocaleString()}</span> empty sites
                        </div>
                    </div>
                    {isAuthenticated
                        ? (<div className="addBtn hidden-xs d-none d-sm-block">
                            <Button onClick={() => this.setShowAddTree(true)}>+ Add a Tree</Button>
                        </div>)
                        : ''
                    }
                </div>
            </div>
            <div className={`content explore-map ${showAddTree ? "hide-search" : ""}`}>
                <Map
                    className="map"
                    popup={popup}
                    utfEventHandlers={utfEventHandlers}
                    setMap={(m) => this.setState({map: m})}
                    geoRevHash={geoRevHash}
                >
                    <MapEventContainer
                        onClick={this.onMapClick}
                    />
                    {plotTileLayer}
                </Map>
                <div className="sidebar">
                    { sideBar }
                </div>
            </div>
            <Footer />
        </>);
    }
}


function MapEventContainer(props) {
    const { onClick, setMap } = props;
    const map = useMapEvents({
        click: onClick
    });
    return null;
}


function AddTreeMarker(props) {
    const { latLng, updateLatLng } = props;
    const [position, setPosition] = useState(latLng)
    const markerRef = useRef(null)

    // FIXME use the window.settings.staticUrl variable
    const addTreeIcon = new L.Icon({
        iconUrl: '/static/img/mapmarker_viewmode.png',
        iconSize: [78, 75],
        iconAnchor: [36, 62],
    });

    const eventHandlers = useMemo(
        () => ({
            dragend() {
                const marker = markerRef.current
                if (marker != null) {
                    const latLng = marker.getLatLng()
                    updateLatLng(latLng['lat'], latLng['lng']);
                    setPosition(latLng);
                }
            },
        }),
        [],
    )

    return (
        <Marker
            draggable={true}
            eventHandlers={eventHandlers}
            position={position}
            icon={addTreeIcon}
            ref={markerRef} />
    );
}


function ShowFeatureMarker(props) {
    const { latLng, updateLatLng } = props;
    const [position, setPosition] = useState(latLng)
    const markerRef = useRef(null)

    // this can happen if we click on a new marker
    useEffect(() => {
        setPosition(latLng);
    }, [latLng]);

    // FIXME use the window.settings.staticUrl variable
    const addTreeIcon = new L.Icon({
        iconUrl: '/static/img/mapmarker_editmode.png',
        iconSize: [78, 75],
        iconAnchor: [36, 62],
    });

    return (
        <Marker
            position={position}
            icon={addTreeIcon}
            ref={markerRef} />
    );
}
