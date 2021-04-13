import axios from 'axios';

import hmacSHA256 from 'crypto-js/hmac-sha256';
import Base64 from 'crypto-js/enc-base64';

const ACCESS_KEY = 'test_access';
const SECRET_KEY = 'secret key';

export function createSignature(url) {
    const verb = 'GET'
    var urlObject = new URL(url);

    var host = urlObject.host;
    var pathname = urlObject.pathname;
    var searchParams = urlObject.searchParams;

    // now we can add a timestamp and access key
    searchParams.append('access_key', ACCESS_KEY);
    searchParams.append('timestamp', (new Date()).toISOString().split('.')[0]);
    //searchParams.append('timestamp', '2020-12-28T03:02:52');

    var paramString = Array.from(searchParams.entries())
        .map(x => `${x[0]}=${encodeURIComponent(x[1])}`)
        .join('&');

    var stringToSign = [verb, host, pathname, paramString].join('\n');
    var hmacRaw = hmacSHA256(stringToSign, SECRET_KEY);
    var hmac = Base64.stringify(hmacSHA256(stringToSign, SECRET_KEY))
    var hmac2 = Base64.stringify(hmacSHA256(SECRET_KEY, stringToSign));
    searchParams.append('signature', hmac);

    return axios.get(urlObject.toString());
}
