*** Settings ***
Library    SSHLibrary
Resource          api.resource

*** Test Cases ***
Request client certificates on a route
    Run task    module/${MID}/set-route
    ...    {"instance": "x509module", "url": "http://127.0.0.1:2000", "host": "x509.example.org", "http2https": true, "lets_encrypt": false, "client_certificates": true}    decode_json=${FALSE}
    Wait Until Keyword Succeeds    30 seconds    1 second    Route has client certificates    x509module    ${TRUE}

A route keeps its client certificates when it is updated
    Run task    module/${MID}/set-route
    ...    {"instance": "x509module", "url": "http://127.0.0.1:2001", "host": "x509.example.org", "http2https": true, "lets_encrypt": false}    decode_json=${FALSE}
    Wait Until Keyword Succeeds    30 seconds    1 second    Route has client certificates    x509module    ${TRUE}

Client certificates need a host and HTTPS redirection
    Run Keyword And Expect Error    *    Run task    module/${MID}/set-route
    ...    {"instance": "x509broken", "url": "http://127.0.0.1:2000", "path": "/x509", "lets_encrypt": false, "client_certificates": true}

Client certificates can be disabled
    Run task    module/${MID}/set-route
    ...    {"instance": "x509module", "url": "http://127.0.0.1:2001", "host": "x509.example.org", "http2https": true, "lets_encrypt": false, "client_certificates": false}    decode_json=${FALSE}
    Wait Until Keyword Succeeds    30 seconds    1 second    Route has client certificates    x509module    ${FALSE}

A route without the field stays without client certificates
    Run task    module/${MID}/set-route
    ...    {"instance": "x509plain", "url": "http://127.0.0.1:2000", "host": "plain.example.org", "lets_encrypt": false}    decode_json=${FALSE}
    Wait Until Keyword Succeeds    30 seconds    1 second    Route has client certificates    x509plain    ${FALSE}

Remove the routes
    Run task    module/${MID}/delete-route    {"instance": "x509module"}    decode_json=${FALSE}
    Run task    module/${MID}/delete-route    {"instance": "x509plain"}    decode_json=${FALSE}

*** Keywords ***
Route has client certificates
    [Arguments]    ${instance}    ${expected}
    ${response} =    Run task    module/${MID}/get-route    {"instance": "${instance}"}
    Should Be Equal    ${response['client_certificates']}    ${expected}
