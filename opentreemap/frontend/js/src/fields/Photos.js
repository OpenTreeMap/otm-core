import React, { useEffect, useRef, useState, useMemo } from 'react';
import axios from 'axios';
import { Alert, Button } from 'react-bootstrap';

// set an image limit of 20MB
const SIZE_LIMIT = 20 * 1024 * 1024;


export function Photos(props) {
    const { addPhotos, clearPhotos, isEmptyTreePit, treeData, updateTreeData, errors } = props;

    const [showAlert, setShowAlert] = useState(false);

    // pass in the name of the element, the function to use for updating,
    // and the treeDataVariable
    const handleImageUpload = (name) => {
        return (e) => {
            const file = e.target.files[0];

            if (file.size > SIZE_LIMIT) {
                setShowAlert(true);
                return;
            }

            setShowAlert(false);
            addPhotos(name, file);
        }
    }

    return (
        <>
        {showAlert
            ? (<Alert variant="danger" onClose={() => setShowAlert(false)} dismissible>
                <Alert.Heading>Photo Error</Alert.Heading>
                <p>The photo you submitted is too large</p>
            </Alert>)
            : ''
        }
        <div className={errors != null ? 'alert-danger' : ''}>
            <label>* Tree Photos</label>
            <table className="table table-hover">
                <tbody>
                {!isEmptyTreePit
                    ? (<>
                    <PhotoRow
                        title="Add photo of tree shape"
                        buttonText="Add Shape"
                        name="shape"
                        hasPhoto={treeData['has_shape_photo'] == true}
                        handleImageUpload={handleImageUpload("shape")}
                    />
                    <PhotoRow
                        title="Add photo of tree bark"
                        buttonText="Add Bark"
                        name="bark"
                        hasPhoto={treeData['has_bark_photo'] == true}
                        handleImageUpload={handleImageUpload("bark")}
                    />
                    <PhotoRow
                        title="Add photo of tree leaf"
                        buttonText="Add Leaf"
                        name="leaf"
                        hasPhoto={treeData['has_leaf_photo'] == true}
                        handleImageUpload={handleImageUpload("leaf")}
                    /></>)
                    : (<PhotoRow
                        title="Add photo of site"
                        buttonText="Add Site"
                        name="site"
                        hasPhoto={treeData['has_site_photo'] == true}
                        handleImageUpload={handleImageUpload("site")}
                    />)}
                </tbody>
            </table>

            {errors != null
                ? <div className="alert alert-danger text-info">{errors[0]}</div>
                : ''
            }
        </div>
        </>
    );
}


export function PhotoRow(props) {
    const uploader = React.useRef(null);
    const { name, handleImageUpload, title, buttonText, hasPhoto } = props;

    return (
        <tr className={`${hasPhoto ? 'photo-success' : ''}`}>
            <td>{ title }</td>
            <td><input
                    type="file"
                    accept="image/*"
                    multiple="false"
                    name={name}
                    ref={uploader}
                    onChange={handleImageUpload}
                    style={{display: "none"}} />
                <button
                    className="btn add-photos"
                    onClick={() => uploader.current.click()}
                >{ buttonText }</button>
            </td>
        </tr>
    );
}
