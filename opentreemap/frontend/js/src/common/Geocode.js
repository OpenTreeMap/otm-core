import React, { Component, useEffect } from 'react';
import axios from 'axios';

import reverse from 'reverse';
import config from 'treemap/lib/config';

export function geocode(address) {
    try {
        const data = {
            address: address.text,
            key: address.magicKey,
            forStorage: true,
            ...config.instance.extend
        };

        const url = reverse.Urls.geocode();
        return axios.get(url,
            {
                params: data,
                withCredential: true
            });
    } catch (error) {
        return new Promise((resolve, reject) => {
            throw new Error("Could not find the address");
        })
    }
}
