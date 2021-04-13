import React, { useEffect, useRef, useState, useMemo } from 'react';
import axios from 'axios';
import { Button } from 'react-bootstrap';

import { Diameter } from '../fields/Diameter';
import { FieldGroup } from '../fields/FieldGroup';
import { Species } from '../fields/Species';
import { Photos } from '../fields/Photos';

import { useMapEvents } from "react-leaflet";

import reverse from 'reverse';

import utility from 'treemap/lib/utility';
import lonLatToWebMercator from 'treemap/lib/utility';


export function AddTreeSidebar(props) {

    const instance_url = window.django.instance_url;
    const csrfToken = window.django.csrf;

    const { latLng, onClose, map, onMapClick, clearLatLng, onAddMapFeature } = props;
    const [stepNumber, setStepNumber] = useState(1);
    const [ fieldGroups, setFieldGroups ] = useState(null);

    const [ treeData, setTreeData ] = useState({});
    const [ photos, setPhotos ] = useState({});

    const [ saving, setSaving ] = useState(false);

    const [ shouldUseAllSpecies, setShouldUseAllSpecies ] = useState(false);
    const [ isEmptyTreePit, setIsEmptyTreePit ] = useState(false);

    // these are the validation errors from the server
    const [errors, setErrors] = useState({});

    const [featureId, setFeatureId] = useState(0);

    // these are our post-creation pieces
    const [postCreateAction, setPostCreateAction] = useState("addtree-done");

    // clear out only the geometry for adding a new one
    const addTreeSame = (data) => {
        setStepNumber(1);
        clearLatLng();
    }

    // clear our everything to add a new one
    const addTreeNew = (data) => {
        setStepNumber(1);
        setTreeData({});
    }

    const addTreeViewDetails = (data) => {
        // redirect
        const url = reverse.Urls.map_feature_popup_detail({
            instance_url_name: window.django.instance_url,
            feature_id: featureId
        });
        window.location.href = url;
    }

    const addTreeDone = (e) => {
        onClose();
    }

    const updatePostCreateFunction = (e) => {
        setPostCreateAction(e.target.value);
    }

    const postCreateActionMap = {
        'addtree-addsame': (e) => addTreeSame(e),
        'addtree-addnew': (e) => addTreeNew(e),
        'addtree-viewdetails': (e) => addTreeViewDetails(e),
        'addtree-done': (e) => addTreeDone(e)
    }

    const handleErrors = (errors) => {
        const { fieldErrors, globalErrors } = errors;

        setErrors(fieldErrors);
        setStepNumber(2);
    }

    const updateTreeData = (identifier, value) => {
        console.log(`Changed ${identifier} to ${value}`);
        setTreeData({
            ...treeData,
            [identifier]: value,
        });
    }

    const addPhotos = (name, image) => {
        const treeDataVariable = `has_${name}_photo`;
        updateTreeData(treeDataVariable, true);

        setPhotos({
            ...photos,
            [name]: image
        });
    }

    /**
     * Clear out all photo info in the tree data
     */
    const clearPhotos = () => {
        const treeData = Object
            .keys(photos)
            .filter(x => x.match(/has_\w*_photo/))
            .reduce((obj, key) => {obj[key] = false; return obj}, {...treeData})

        setPhotos({});
        setTreeData(treeData);
    }

    const submitPhotos = (data) => {
        console.log(photos);
        const featureId = data.featureId;
        if (isEmptyTreePit) {
            const url = reverse.Urls.add_photo_to_map_feature({
                instance_url_name: window.django.instance_url,
                feature_id: featureId
            });
            return axios.post(url,
                {'file': null},
                {withCredential: true, headers: {"X-CSRFToken": csrfToken}});
        }

        const url = reverse.Urls.add_photo_to_tree_with_label({
            instance_url_name: window.django.instance_url,
            feature_id: featureId,
            tree_id: data.treeId
        });

        return axios.all(Object.keys(photos).map(x => {
            const formData = new FormData();
            formData.append('label', x);
            formData.append('file', photos[x]);
            return axios.post(url, formData,
                {withCredential: true,
                 headers: {'X-CSRFToken': csrfToken, 'Content-Type': 'multipart/form-data'}
                });
        }));
    }

    useEffect(() => {
        var url = `/${instance_url}/fields/`;
        axios.get(url, {withCredential: true})
            .then(res => {
                let fieldGroups = res.data.field_groups;
                setFieldGroups(fieldGroups);

                // set our initial tree data as all empty
                let initialFields = fieldGroups
                    .flatMap(x => x.fields)
                    .reduce((_map, field) => {
                        _map[field.identifier] = field.value || "";
                        return _map;
                    }, {});
                // zip together the collection_udf_keys and the collection_udfs
                let collectionUdfs = fieldGroups
                    .flatMap(fg => fg.collection_udf_keys
                        .map((k, i) => [k, fg.collection_udfs[i]]))
                    .reduce((_map, udf) => {
                        _map[udf[0]] = udf[1].iscollection ? [] : "";
                        return _map;
                    }, {});

                setTreeData({
                    ...initialFields,
                    ...collectionUdfs
                });
            }).catch(res => {
                console.log('error');
                console.log(res);
            });
    }, []);


    const closeHandler = (e) => {
        e.preventDefault();
        onClose();
    }

    const onComplete = () => {
        console.log(treeData);
        const treeDataFormatted = {
            // fix the dates, because we don't want to fix them on the backend yet
            ...Object.keys(treeData).reduce((obj, key) => {
                const value = treeData[key];
                obj[key] = value instanceof Date
                    ? value.toISOString().split('T')[0]
                    : value;
                return obj
            }, treeData),
            "plot.geom": {
                "y": latLng.lat,
                "x": latLng.lng,
                "srid": 4326
            },
            // species for the server is just the ID
            "tree.species": treeData["tree.species"]?.id,
            "is_empty_site": isEmptyTreePit
        }

        const url = reverse.Urls.addPlot(instance_url);
        setSaving(true);
        axios.post(url,
                treeDataFormatted,
                {withCredential: true, headers: {"X-CSRFToken": csrfToken}},
            ).then(res => {
            /*
                console.log('submitted tree');
                console.log(res);
                setFeatureId(res.data.featureId);
                return submitPhotos(res.data);
            }).then(res => {
            */
                onAddMapFeature(res.data);
                postCreateActionMap[postCreateAction](res.data);
                setFeatureId(0);
                setSaving(false);
            }).catch(err => {
                handleErrors(err.response.data);
                setFeatureId(0);
                setSaving(false);
            });
    }

    const step = stepNumber == 1
        ? <FirstStep
            closeHandler={onClose}
            map={map}
            onMapClick={onMapClick}
            latLng={latLng}
            onNext={() => setStepNumber(2)} />
        : stepNumber == 2
        ? <SecondStep
            latLng={latLng}
            closeHandler={onClose}
            fieldGroups={fieldGroups}
            updateTreeData={updateTreeData}
            treeData={treeData}
            addPhotos={addPhotos}
            clearPhotos={clearPhotos}
            shouldUseAllSpecies={shouldUseAllSpecies}
            setShouldUseAllSpecies={setShouldUseAllSpecies}
            isEmptyTreePit={isEmptyTreePit}
            setIsEmptyTreePit={setIsEmptyTreePit}
            errors={errors}
            //onComplete={() => onComplete()}
            onNext={() => setStepNumber(3)}
            onPrevious={() => setStepNumber(1)}/>
        : stepNumber == 3
        ? <ThirdStep
            closeHandler={onClose}
            treeData={treeData}
            updatePostCreateFunction={updatePostCreateFunction}
            postCreateAction={postCreateAction}
            onComplete={() => onComplete()}
            onPrevious={() => setStepNumber(2)}
            saving={saving}
        />
        : null;

    return (
        <div id="sidebar-add-tree">
            <div className="sidebar-inner">
                <a
                    className="close cancelBtn small d-none d-sm-block"
                    style={{zIndex: 99}}
                    onClick={closeHandler}>×</a>
                <h3>Add a Tree</h3>
                {step}
            </div>
        </div>
    );
}


function Step(props) {
    const { closeHandler, latLng, stepNumber } = props;
    // disable going to the next step until we complete our location
    const nextDisabled = stepNumber == 1 && latLng.lat == null && latLng.lng == null;
    return (
        <div className="add-step-container">
            <div className={`add-step ${props.withMap ? "with-map" : ""} active`}>
                <div className="add-step-header">
                    {props.stepHeader || ''}
                    <a
                        className="close cancelBtn small d-block d-sm-none"
                        style={{zIndex: 99}}
                        onClick={closeHandler}>×</a>
                </div>
                <div className="add-step-content"> {props.children} </div>
                <div className="add-step-footer">

                    <ul className="pagination justify-content-center">
                        <li className="page-item">
                        {stepNumber != 1
                            ? <a className="btn btn-primary page-link" onClick={props.onPrevious}>Back</a>
                            : ''
                        }
                        </li>
                        <li className="page-item disabled">
                            <span className="page-link">Step {stepNumber} of 3</span>
                        </li>
                        <li className="page-item">
                        {props.stepNumber != 3
                            ? <a
                                className={`page-link btn ${nextDisabled ? "btn-secondary" : "btn-primary"}`}
                                onClick={nextDisabled ? null : props.onNext}>Next</a>
                            : <a className="page-link btn btn-primary" onClick={props.onComplete}>Done</a>
                        }
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );

}


function FirstStep(props) {
    const { map, onMapClick } = props;
    //const [position, setPosition] = useState(null);
    //const markerRef = useRef(null);

    /*
    const eventHandlers = useMemo(
        () => ({
            dragend() {
                const marker = markerRef.current;
                if (marker != null) {
                    setPosition(marker.getLatLng());
                }
            }
        }),
        [],
    );
    */

    const onLocationFound = (e) => {
        map.flyTo(e.latlng, map.getZoom());
        onMapClick(e);
    }

    useEffect(() => {
        if (map != null) {
            map.on('locationfound', onLocationFound)
        }
    }, [map]);

    const stepHeader = "1. Set the tree's location";
    /*
        <input type="text" className="form-control tt-input" placeholder="Address" />
        <button className="btn geocode">Search</button>
    */
    return (
        <Step
            stepNumber={1}
            stepHeader={stepHeader}
            withMap={true}
            {...props}
        >
        <form className="form-inline">
        </form>
        <div>
            <a className="geolocate" onClick={() => map.locate()}><i className="icon-direction"></i> Use current location</a>
        </div>

        <div className="alert alert-info move-market-message hidden-xs d-none d-sm-block">
            Choose a point on the map or select "Use Current Location"
        </div>

        <div className="alert alert-info move-market-message hidden-xs d-none d-sm-block">
            Please move marker to the exact location of the tree.
        </div>
        </Step>
    );
}


function SecondStep(props) {
    const stepHeader = "2. Add species and additional info";
    const {
        fieldGroups,
        updateTreeData,
        treeData,
        addPhotos,
        clearPhotos,
        errors,
        shouldUseAllSpecies,
        setShouldUseAllSpecies,
        isEmptyTreePit,
        setIsEmptyTreePit
    } = props;

    if (!fieldGroups) return (<div>Loading...</div>);

    const fieldGroupsTree = fieldGroups.find(x => x.model == 'tree')

    // filter these out diameter and species and handle them separately
    const diameter = 'tree.diameter';
    const diameterFieldProps = fieldGroupsTree?.fields.find(x => x.identifier == diameter);
    const diameterField = diameterFieldProps
        ? <Diameter
            identifier={diameter}
            updateTreeData={updateTreeData}
            treeData={treeData}
            errors={errors != null ? errors[diameter] : null}
            {...diameterFieldProps} />
        : '';

    const species = 'tree.species';
    const speciesFieldProps = fieldGroupsTree?.fields.filter(x => x.identifier == diameter)
    const speciesField = speciesFieldProps
        ? <Species
            identifier={species}
            updateTreeData={updateTreeData}
            treeData={treeData}
            shouldUseAllSpecies={shouldUseAllSpecies}
            setShouldUseAllSpecies={setShouldUseAllSpecies}
            isEmptyTreePit={isEmptyTreePit}
            setIsEmptyTreePit={setIsEmptyTreePit}
            errors={errors != null ? errors[species] : null}
            {...speciesFieldProps} />
        : '';

    return (
        <Step
            stepNumber={2}
            stepHeader={stepHeader}
            {...props}
        >
            <Photos
                updateTreeData={updateTreeData}
                treeData={treeData}
                isEmptyTreePit={isEmptyTreePit}
                addPhotos={addPhotos}
                clearPhotos={clearPhotos}
                errors={errors != null ? errors['tree.photos'] : null}
            />

            <hr />

            {speciesField}

            <hr />

            {diameterField}

            <hr />

            {fieldGroups.map((fieldGroup, i) => <FieldGroup
                key={i}
                fieldGroup={fieldGroup}
                updateTreeData={updateTreeData}
                treeData={treeData}
                errors={errors}
                filterFields={[diameter, species]} />)}
        </Step>
    );
}


function ThirdStep(props) {
    const stepHeader = "3. Finalize this tree"
    const { updatePostCreateFunction, postCreateAction, saving } = props

    return (
        <Step
            stepNumber={3}
            stepHeader={stepHeader}
            {...props}
        >
            <hr />
            <label>After I add this tree...</label>
        {saving
            ? <div><img className="spinner" src='/static/img/spinner.gif' />Saving...</div>
            : ''
        }
        <div>
            <input
                type="radio"
                name="addFeatureOptions"
                id="addtree-addsame"
                value="addtree-addsame"
                checked={postCreateAction == "addtree-addsame"}
                onChange={updatePostCreateFunction}
            />
            <label htmlFor="addtree-addsame">Add another tree with these details</label>
        </div>
        <div>
            <input
                type="radio"
                name="addFeatureOptions"
                id="addtree-addnew"
                value="addtree-addnew"
                checked={postCreateAction == "addtree-addnew"}
                onChange={updatePostCreateFunction}
            />
            <label htmlFor="addtree-addnew">Add another tree with new details</label>
        </div>
        <div>
            <input
                type="radio"
                name="addFeatureOptions"
                id="addtree-viewdetails"
                value="addtree-viewdetails"
                checked={postCreateAction == "addtree-viewdetails"}
                onChange={updatePostCreateFunction}
            />
            <label htmlFor="addtree-viewdetails">Continue editing this tree</label>
        </div>
        <div>
            <input
                type="radio"
                name="addFeatureOptions"
                id="addtree-done"
                value="addtree-done"
                checked={postCreateAction == "addtree-done"}
                onChange={updatePostCreateFunction}
            />
            <label htmlFor="addtree-done">I'm done!</label>
        </div>
        </Step>
    );
}
