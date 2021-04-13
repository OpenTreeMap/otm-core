import React, { useState } from 'react';
import { AsyncTypeahead } from 'react-bootstrap-typeahead';
import axios from 'axios';

import config from 'treemap/lib/config';
import { geocode } from './Geocode';


export function GeolocateTypeahead(props) {
    const { onLocationFound } = props;

    const [ options, setOptions] = useState([]);
    const [ errors, setErrors ] = useState(null);
    const [ address, setAddress ] = useState(null);
    const [ isLoading, setIsLoading ] = useState(false);
    const url = 'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/suggest?f=json';

    const handleSearch = (query) => {
        setIsLoading(true);
        const searchExtent = {
            spatialReference: {wkid: 102100},
            ...config.instance.extent
        };
        const urlWithQuery = `${url}&searchExtent=${encodeURI(JSON.stringify(searchExtent))}&text=${query}`;
        axios.get(urlWithQuery)
            .then(res => {
                setOptions(res.data?.suggestions || []);
                setErrors(null);
                setIsLoading(false);
            }).catch(err => {
                console.log(err);
                setOptions([]);
                setErrors(null);
                setIsLoading(false);
            });
    }

    const searchAddress = () => {
        if (address == null || address.length == 0) {
            setErrors(["Could not find address"]);
            return;
        }

        setErrors(null);

        geocode(
            address[0]
        ).then(res => {
            onLocationFound({latlng: res.data});
            setErrors(null);
        }).catch(err => {
            setErrors(err);
        });
    }

    return (
        <form className="form-inline">
            <AsyncTypeahead
                id="geocode-typeahead"
                placeholder="Address"
                options={options}
                minLength={3}
                onSearch={handleSearch}
                isLoading={isLoading}
                labelKey="text"
                onChange={(e) => {
                    setAddress(e);
                }}
            />
            <a className="btn geocode" onClick={() => searchAddress()}>Search</a>
        {errors != null
            ? <div>Could not find address</div>
            : ''
        }
        </form>
    );
}
