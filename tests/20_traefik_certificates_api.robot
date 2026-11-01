*** Settings ***
Library    SSHLibrary
Resource          api.resource

*** Test Cases ***

Get default ACME server
    ${response} =  Run task    module/${MID}/get-acme-server    {}
    Should Be Equal As Strings    ${response['url']}        https://acme-v02.api.letsencrypt.org/directory


Set ACME server url to Let's Encrypt Staging
    ${response} =  Run task    module/${MID}/set-acme-server
    ...    {"url":"https://acme-staging-v02.api.letsencrypt.org/directory"}

Get configured ACME server
    ${response} =  Run task    module/${MID}/get-acme-server    {}
    Should Be Equal As Strings    ${response['url']}        https://acme-staging-v02.api.letsencrypt.org/directory

Request an invalid certificate with set-certificate
    ${response} =  Run task    module/${MID}/set-certificate
    ...    {"fqdn":"first.example.com"}    decode_json=${False}    rc_expected=3
    Should Contain    ${response}    newcert_acme_error

Get invalid certificate status obtained by set-certificate
    ${response} =  Run task    module/${MID}/get-certificate    {"fqdn": "first.example.com"}
    Should Be Equal As Strings    ${response['type']}    selfsigned

Request an invalid certificate with set-default-certificate
    ${response} =  Run task    module/${MID}/set-default-certificate
    ...    {"names": ["second.example.com"]}    decode_json=${False}    rc_expected=3
    Should Contain    ${response}    newcert_acme_error

Get invalid certificate status obtained by set-default-certificate
    ${response} =  Run task    module/${MID}/get-certificate    {"fqdn": "second.example.com"}
    Should Be Equal As Strings    ${response['type']}    selfsigned

Get certificate list
    ${response} =  Run task    module/${MID}/list-certificates    ""
    Should Be Empty    ${response['certificates']}

Delete invalid certificate
    ${response} =  Run task    module/${MID}/delete-certificate
    ...    {"serial": "UNKNOWN-EXAMPLE.COM","type":"internal"}    decode_json=${False}    rc_expected=2

Get empty certificates list
    ${response} =  Run task    module/${MID}/list-certificates    ""
    Should Be Empty    ${response['certificates']}

Reject a certificate with missing or empty CN field
    ${plain_key} =    Execute Command    openssl genrsa 4096
    ${plain_csr} =    Execute Command    echo "${plain_key}" \| openssl req -key /dev/stdin -x509 -sha256 -days 3650 -nodes -subj "/CN=/O=YourOrganization/OU=YourUnit"  -addext "subjectAltName=DNS:test.example.com"
    # base64 encode the key and csr
    ${encoded_key} =    Execute Command    echo "${plain_key}" \| base64 -w 0
    ${encoded_csr} =    Execute Command    echo "${plain_csr}" \| base64 -w 0
    ${response} =  Run task    module/${MID}/upload-certificate
    ...    {"keyFile": "${encoded_key}", "certFile": "${encoded_csr}"}    rc_expected=5    decode_json=False

Generate a custom private and public key
    ${plain_key} =    Execute Command    openssl genrsa 4096
    ${plain_csr} =    Execute Command    echo "${plain_key}" \| openssl req -key /dev/stdin -x509 -sha256 -days 3650 -nodes -subj "/CN=test.example.com"  -addext "subjectAltName=DNS:test.example.com"
    # base64 encode the key and csr
    ${encoded_key} =    Execute Command    echo "${plain_key}" \| base64 -w 0
    ${encoded_csr} =    Execute Command    echo "${plain_csr}" \| base64 -w 0
    Set Suite Variable    ${key}   ${encoded_key}
    Set Suite Variable    ${csr}   ${encoded_csr}

Upload rejected for a self-signed certificate
    ${response} =  Run task    module/${MID}/upload-certificate
    ...    {"keyFile": "${key}", "certFile": "${csr}"}    rc_expected=33

Upload a custom certificate
    # Disable strict certificate verification:
    Execute Command    runagent -m ${MID} python3 -c 'import agent ; agent.set_env("UPLOAD_CERTIFICATE_VERIFY_TYPE", "selfsign")'
    ${response} =  Run task    module/${MID}/upload-certificate
    ...    {"keyFile": "${key}", "certFile": "${csr}"}
    ${response} =  Run task    module/${MID}/get-certificate    {"fqdn": "test.example.com"}
    Should Be Equal As Strings    ${response['fqdn']}        test.example.com
    Should Be Equal As Strings    ${response['obtained']}    True
    Should Be Equal As Strings    ${response['type']}    custom
    # check if the certificate is stored in redis
    ${response} =    Execute Command    redis-cli --raw EXISTS module/${MID}/certificate/test.example.com
    Should Be Equal As Integers    ${response}    1
    ${response} =    Execute Command    redis-cli --raw HGET module/${MID}/certificate/test.example.com custom
    Should Be Equal As Strings    ${response}    true
    # check if the certificate stored is base64 encoded
    ${response} =    Execute Command    command=redis-cli HGET module/${MID}/certificate/test.example.com cert | base64 -d    return_stdout=False    return_rc=True
    Should Be Equal As Integers    ${response}    0
    ${response} =    Execute Command    command=redis-cli HGET module/${MID}/certificate/test.example.com key | base64 -d    return_stdout=False    return_rc=True
    Should Be Equal As Integers    ${response}    0
    Execute Command    runagent -m ${MID} python3 -c 'import agent ; agent.set_env("UPLOAD_CERTIFICATE_VERIFY_TYPE", "chain")'

Delete custom certificate
    Run task    module/${MID}/delete-certificate   	 {"path": "custom_certificates/test.example.com.crt","type":"custom"}
    ${response} =    Execute Command    redis-cli --raw EXISTS module/${MID}/certificate/test.example.com
    Should Be Equal As Integers    ${response}    0
