import React, { useEffect, useRef, useState } from 'react';
import { TileLayer, Marker, Popup } from "react-leaflet";
import axios from 'axios';
import reverse from 'reverse';


export function TreePopup(props) {
    const { latLng, ids } = props;
    const [title, setTitle] = useState(null);
    const [canEdit, setCanEdit] = useState(false);
    const instance_url = window.django.instance_url;

    useEffect(() => {
        // clear the title before loading a new one
        //var url = `/${instance_url}/features/${ids[0]}/popup_detail`;
        const url = reverse.Urls.map_feature_popup_detail({
            instance_url_name: window.django.instance_url,
            feature_id: ids[0]
        });
        setTitle(null);
        setCanEdit(false);
        axios.get(url, {withCredential: true})
            .then(res => {
                const feature = res.data.features[0];
                setTitle(res.data.features[0].title);
                setCanEdit(window.django.user.is_authenticated
                    && feature.is_plot
                    && feature.is_editable);
            }).catch(res => {
                setTitle(null);
                setCanEdit(false);
            });
    }, [ids]);

    if (title == null) {
        return (
            <Popup position={latLng}>
                Loading...
            </Popup>
        );
    }

    const featureUrl = reverse.Urls.map_feature_detail({
        instance_url_name: instance_url,
        feature_id: ids[0]
    });

    const featureEditUrl = reverse.Urls.map_feature_detail_edit({
        instance_url_name: instance_url,
        feature_id: ids[0],
        edit: 'edit'
    });
    const isEmbedded = new URLSearchParams(window.location.search).get('embed') == "1";

    return (
        <Popup position={latLng}>
            <div id="map-feature-content">
                <div className="popup-content">
                    <h4>{title}</h4>
                    <div className="popup-btns">
                        {!isEmbedded
                            ? (<a href={featureUrl} className="btn btn-sm btn-secondary">More Details</a>)
                            : (<a href={featureUrl} target="_blank" className="btn btn-sm btn-secondary">More Details</a>)
                        }
                        { !isEmbedded && canEdit
                            ? <a href={featureEditUrl} className="btn btn-sm btn-info">Edit</a>
                            : ""
                        }
                    </div>
                </div>
            </div>
        </Popup>
    );
}
