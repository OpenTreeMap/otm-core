import React, { useEffect, useRef, useState, useMemo } from 'react';
import axios from 'axios';
import { Button } from 'react-bootstrap';

import { ClearButton, Typeahead } from 'react-bootstrap-typeahead';
import 'react-bootstrap-typeahead/css/Typeahead.css';


/**
 * Show the title of the species using the common name and the scientific name
 */
export function SpeciesTitle(props) {
    const { commonName, scientificName } = props;

    return (
        <div className="tree-details-species" data-class="display">
            <h3>{commonName}</h3>
            <h5>
                <em>{scientificName}</em>
            </h5>
        </div>
    );
}


export function Species(props) {
    const {
        identifier,
        updateTreeData,
        treeData,
        shouldUseAllSpecies,
        setShouldUseAllSpecies,
        isEmptyTreePit,
        setIsEmptyTreePit,
        errors
    } = props;

    const [ species, setSpecies ] = useState(treeData[identifier] || null);
    const [ commonSpecies, setCommonSpecies ] = useState([]);
    const [ allSpecies, setAllSpecies ] = useState([]);

    const ref = useRef();

    useEffect(() => {
        axios.get('/jerseycity/species/?is_common=true', {withCredential: true})
            .then(x => {
                setCommonSpecies(x.data);
            }).catch(x => {
                console.log('Error getting species');
            });
    }, []);

    useEffect(() => {
        if (shouldUseAllSpecies && allSpecies.length == 0){
            axios.get('/jerseycity/species', {withCredential: true})
                .then(x => {
                    setAllSpecies(x.data);
                }).catch(x => {
                    console.log('Error getting all species');
                });
        }
    }, [shouldUseAllSpecies]);

    const onChangeEmptyTreePit = (e) => {
        const { checked, name } = e.target;
        setIsEmptyTreePit(checked);
        if (checked) {
            setSpecies(null);
            ref.current.clear();
        }
    }

    return (
        <div className={errors != null ? 'alert-danger' : ''}>
            <label>* Species</label>
            <div>
                <Typeahead
                    id="species-typeahead"
                    placeholder="Common or scientific name"
                    options={shouldUseAllSpecies ? allSpecies : commonSpecies}
                    labelKey="value"
                    disabled={isEmptyTreePit}
                    selected={species ? [species] : null}
                    renderMenuItemChildren={(option, props, index) => {
                        return (
                            <div className="tt-suggestion tt-selectable">
                                {option.common_name}
                                <small>
                                    {option.scientific_name}
                                </small>
                            </div>
                        );
                    }}
                    clearButton={true}
                    ref={ref}
                    onChange={(e) => {
                        const species = e[0];
                        setSpecies(species);
                        updateTreeData(identifier, species);
                    }}
                />
            <input
                type="checkbox"
                name="allSpecies"
                id="allSpecies"
                checked={shouldUseAllSpecies}
                onChange={(e) => setShouldUseAllSpecies(e.target.checked)}
            />
            <label htmlFor="allSpecies">Make all species available</label>
            <br />
            <input
                type="checkbox"
                name="is_empty_site"
                id="is-empty-site"
                checked={isEmptyTreePit}
                onChange={onChangeEmptyTreePit}
            />
            <label htmlFor="is-empty-site">Is Empty Site</label>
            </div>

            {errors != null
                ? <div className="alert alert-danger text-info">{errors[0]}</div>
                : ''
            }
        </div>
    );
}

