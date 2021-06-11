import React from 'react';

export function Footer(props) {
    const isEmbedded = new URLSearchParams(window.location.search).get('embed') == "1";
    if (isEmbedded) return '';

    return (
        <footer className="hidden-xs d-none d-sm-block">
            <div className="footer-inner">
                <ul className="list-inline pull-left">
                    <li><a target="_blank" href="http://www.arborday.org/trees/whatTree/">Tree ID</a></li>
                    <li><a target="_blank" href="http://www.arborday.org/trees/whatTree/">Tree ID2</a></li>
                </ul>
            </div>
        </footer>
    );
}
