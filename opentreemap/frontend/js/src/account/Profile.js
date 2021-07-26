import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import config from 'treemap/lib/config';
import reverse from 'reverse';

import './Profile.css';

import { Line, Bar } from 'react-chartjs-2';


export default function Profile(props) {
    return (
        <div className="container contained profile">
            <h3>My Dashboard</h3>
            <div className="row">
                <div className="col-md-9">
                    <MyTotalTrees />
                </div>

                <div className="col-md-6 profile-container">
                    <h3>My Trees Over Time (By Week)</h3>
                    <div className="line">
                        <MyTreesOverTime />
                    </div>
                </div>

                <div className="col-md-6 profile-container">
                    <h3>My Trees By Neighborhood</h3>
                    <div className="line">
                        <MyTreesByNeighborhood />
                    </div>
                </div>

                <div className="col-md-9 profile-container">
                    <h3>My Realized EcoBenefits</h3>
                    <MyEcobenefits />
                </div>
            </div>
        </div>
    );
}


function MyTreesOverTime(props) {
    const [data, setData] = useState({
        labels: [],
        datasets: [],
    });

    var options = {
        maintainAspectRatio: false,
        scales: {
            xAxes: [{
                title: "time",
                type: 'time',
                gridLines: {
                    lineWidth: 2
                },
                time: {
                    unit: "day",
                    unitStepSize: 1000,
                    displayFormats: {
                        millisecond: 'MMM DD',
                        second: 'MMM DD',
                        minute: 'MMM DD',
                        hour: 'MMM DD',
                        day: 'MMM DD',
                        week: 'MMM DD',
                        month: 'MMM DD',
                        quarter: 'MMM DD',
                        year: 'MMM DD',
                    }
                }
            }]
        }
    }

    useEffect(() => {
        const url = reverse.Urls.get_reports_user_data(config.instance.url_name)
        axios.get(url, {withCredential: true, params: {data_set: 'count_over_time'}})
            .then(res => {
                setData({
                    labels: res.data.data.map(x => (new Date(x.name).toLocaleDateString('en-US'))),
                    datasets: [{
                        data: res.data.data.map(x => x.count),
                        label: "Trees By Week",
                        borderColor: '#8baa3d',
                        backgroundColor: '#8baa3d',
                    }]
                });
            });
    }, []);

    return (<Line data={data} options={options}/>);
}


function MyTreesByNeighborhood(props) {
    const [data, setData] = useState({
        labels: [],
        datasets: []
    });

    var options = {
        maintainAspectRatio: false,
    }

    useEffect(() => {
        const url = reverse.Urls.get_reports_user_data(config.instance.url_name)
        axios.get(url, {withCredential: true, params: {data_set: 'count', aggregation_level: 'neighborhood'}})
            .then(res => {
                setData({
                    labels: res.data.data.map(x => x.name),
                    datasets: [{
                        data: res.data.data.map(x => x.count),
                        label: "Trees By Neighborhood",
                        borderColor: '#8baa3d',
                        backgroundColor: '#8baa3d',
                    }]
                });
            });
    }, []);

    return (
        <Bar data={data} options={options} />

    );
}


function MyTotalTrees(props) {
    const [count, setCount] = useState(null);

    useEffect(() => {
        const url = reverse.Urls.get_reports_user_data(config.instance.url_name)
        axios.get(url, {withCredential: true, params: {data_set: 'count'}})
            .then(res => {
                setCount(res.data.data[0].count);
            });
    }, []);
    return (
        <div className="circle-tile">
            <div className="circle-tile-content">
                <div className="circle-tile-description text-faded">My Total Trees / Tree Pits</div>
                <div className="circle-tile-number text-faded ">{count}</div>
            </div>
        </div>
    );
}


function MyEcobenefits(props) {
    const [benefits, setBenefits] = useState({});

    var formatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',

        // These options are needed to round to whole numbers if that's what you want.
        //minimumFractionDigits: 0, // (this suffices for whole numbers, but will print 2500.10 as $2,500.1)
        //maximumFractionDigits: 0, // (causes 2500.99 to be printed as $2,501)
    });

    useEffect(() => {
        const url = reverse.Urls.get_reports_user_data(config.instance.url_name)
        axios.get(url, {withCredential: true, params: {data_set: 'ecobenefits_by_user'}})
            .then(res => {
                const data = res.data.data.data;
                const columns = res.data.data.columns;
                const benefits = columns
                    .map((col, i) => [col, data[i]])
                    .filter(x => x[0] != 'Name')  // remove the name field as it won't be a table
                    .reduce((_map, x) => {_map[x[0]] = x[1]; return _map;}, {})
                setBenefits(benefits);
            });
    }, []);

    return (
        <div>
            <table className="table center-table">
                {Object.keys(benefits).map(key => {
                    const value = key.indexOf('$') == -1
                        ? benefits[key].toLocaleString('en-US', {maximumFractionDigits: 2})
                        : formatter.format(benefits[key]);

                    return (
                        <tr>
                            <td>{key}</td>
                            <td>{value}</td>
                        </tr>
                    );
                })}
            </table>
        </div>
    );

}
