*** Settings ***
Library    SSHLibrary
Library    Collections
Resource          api.resource

*** Test Cases ***
Create a path rule
    ${response} =  Run task    module/${MID}/set-route
    ...    {"instance": "module1", "url": "http://127.0.0.0:2000", "path": "/foo", "lets_encrypt": false, "http2https": true, "skip_cert_verify": true, "headers": {"request": {"X-foo-add": "foo", "X-bar-remove": ""}, "response": {"X-bar-add": "bar", "X-foo-remove": ""}}}

Create a host rule
    ${response} =  Run task    module/${MID}/set-route
    ...    {"instance": "module2", "url": "http://127.0.0.0:2000", "host": "foo.example.org", "lets_encrypt": true, "http2https": true, "skip_cert_verify": true, "headers": {"request": {"X-foo-add": "foo", "X-bar-remove": ""}, "response": {"X-bar-add": "bar", "X-foo-remove": ""}}}

Create a host & path rule
    ${response} =  Run task    module/${MID}/set-route
    ...    {"instance": "module3", "url": "http://127.0.0.0:2000", "host": "bar.example.org", "path": "/bar", "lets_encrypt": true, "http2https": true, "skip_cert_verify": true, "user_created": true, "headers": {"request": {"X-foo-add": "foo", "X-bar-remove": ""}, "response": {"X-bar-add": "bar", "X-foo-remove": ""}}}

Create an invalid path route
    Run Keyword And Expect Error    *    Run task    module/${MID}/set-route
    ...    {"instance": "module4", "url": "http://127.0.0.0:2000", "path": "bar", "lets_encrypt": true, "http2https": true, "skip_cert_verify": true, "headers": {"request": {"X-foo-add": "foo", "X-bar-remove": ""}, "response": {"X-bar-add": "bar", "X-foo-remove": ""}}}

Create a host rule with forward auth
    ${response} =  Run task    module/${MID}/set-route
    ...    {"instance": "module5", "url": "http://127.0.0.0:2000", "host": "foo.example.org", "lets_encrypt": true, "http2https": true, "skip_cert_verify": true, "headers": {"request": {"X-foo-add": "foo", "X-bar-remove": ""}, "response": {"X-bar-add": "bar", "X-foo-remove": ""}}, "forward_auth": { "address": "http://127.0.0.1:9311/api/module/module1/http-basic/add-module1", "skip_tls_verify": true, "auth_response_headers": [ "X-Auth-User"] }}


Get path route
    ${response} =  Run task    module/${MID}/get-route    {"instance": "module1"}
    Should Be Equal As Strings    ${response['instance']}        module1
    Should Be Equal As Strings    ${response['path']}            /foo
    Should Be Equal As Strings    ${response['url']}              http://127.0.0.0:2000
    Should Be Equal As Strings    ${response['lets_encrypt']}    False
    Should Be Equal As Strings    ${response['http2https']}      True
    Should Be Equal As Strings    ${response['skip_cert_verify']}  True
    Should Be Equal As Strings    ${response['strip_prefix']}    False
    Should Be Equal As Strings    ${response['user_created']}    False
    Should Be Equal As Strings    ${response['headers']['request']['X-foo-add']}    foo
    Should Be Equal As Strings    ${response['headers']['request']['X-bar-remove']}    ${EMPTY}
    Should Be Equal As Strings    ${response['headers']['response']['X-bar-add']}    bar
    Should Be Equal As Strings    ${response['headers']['response']['X-foo-remove']}    ${EMPTY}

Get host route
    ${response} =  Run task    module/${MID}/get-route    {"instance": "module2"}
    Should Be Equal As Strings    ${response['instance']}        module2
    Should Be Equal As Strings    ${response['host']}            foo.example.org
    Should Be Equal As Strings    ${response['url']}             http://127.0.0.0:2000
    Should Be Equal As Strings    ${response['lets_encrypt']}    True
    Should Be Equal As Strings    ${response['http2https']}      True
    Should Be Equal As Strings    ${response['skip_cert_verify']}  True
    Should Be Equal As Strings    ${response['user_created']}    False
    Should Be Equal As Strings    ${response['headers']['request']['X-foo-add']}    foo
    Should Be Equal As Strings    ${response['headers']['request']['X-bar-remove']}    ${EMPTY}
    Should Be Equal As Strings    ${response['headers']['response']['X-bar-add']}    bar
    Should Be Equal As Strings    ${response['headers']['response']['X-foo-remove']}    ${EMPTY}


Get host & path route
    ${response} =  Run task    module/${MID}/get-route    {"instance": "module3"}
    Should Be Equal As Strings    ${response['instance']}        module3
    Should Be Equal As Strings    ${response['path']}            /bar
    Should Be Equal As Strings    ${response['host']}            bar.example.org
    Should Be Equal As Strings    ${response['url']}              http://127.0.0.0:2000
    Should Be Equal As Strings    ${response['lets_encrypt']}    True
    Should Be Equal As Strings    ${response['http2https']}      True
    Should Be Equal As Strings    ${response['skip_cert_verify']}  True
    Should Be Equal As Strings    ${response['strip_prefix']}    False
    Should Be Equal As Strings    ${response['user_created']}    True
    Should Be Equal As Strings    ${response['headers']['request']['X-foo-add']}    foo
    Should Be Equal As Strings    ${response['headers']['request']['X-bar-remove']}    ${EMPTY}
    Should Be Equal As Strings    ${response['headers']['response']['X-bar-add']}    bar
    Should Be Equal As Strings    ${response['headers']['response']['X-foo-remove']}    ${EMPTY}

Get routes list
    ${response} =  Run task    module/${MID}/list-routes    null
    Should Contain    ${response}    module1
    Should Contain    ${response}    module2
    Should Contain    ${response}    module3
    Should Contain    ${response}    cluster-admin

Get expanded routes list
    ${response} =  Run task    module/${MID}/list-routes    {"expand_list": true}
    ${routes_length} =         Get Length    ${response}
    FOR    ${I}    IN RANGE    ${routes_length}
        IF             $response[$I]['instance'] == "cluster-admin"
            Should Be Equal As Strings    ${response[${I}]['path']}            /cluster-admin
            Should Be Equal As Strings    ${response[${I}]['url']}             http://127.0.0.1:9311
            Should Be Equal As Strings    ${response[${I}]['lets_encrypt']}    False
            Should Be Equal As Strings    ${response[${I}]['http2https']}      True
            Should Be Equal As Strings    ${response[${I}]['skip_cert_verify']}  False
            Should Be Equal As Strings    ${response[${I}]['strip_prefix']}    True
            Should Be Equal As Strings    ${response[${I}]['slash_redirect']}  True
            Should Be Equal As Integers   ${response[${I}]['priority']}        100000
            Should Be Equal As Strings    ${response[${I}]['user_created']}    False
        ELSE IF        $response[$I]['instance'] == "module1"
            Should Be Equal As Strings    ${response[${I}]['slash_redirect']}  False
            Should Be Equal As Integers   ${response[${I}]['priority']}        1
            Should Be Equal As Strings    ${response[${I}]['path']}            /foo
            Should Be Equal As Strings    ${response[${I}]['url']}             http://127.0.0.0:2000
            Should Be Equal As Strings    ${response[${I}]['lets_encrypt']}    False
            Should Be Equal As Strings    ${response[${I}]['http2https']}      True
            Should Be Equal As Strings    ${response[${I}]['skip_cert_verify']}  True
            Should Be Equal As Strings    ${response[${I}]['strip_prefix']}    False
            Should Be Equal As Strings    ${response[${I}]['user_created']}    False
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-foo-add']}    foo
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-bar-remove']}    ${EMPTY}
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-bar-add']}    bar
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-foo-remove']}    ${EMPTY}
        ELSE IF        $response[$I]['instance'] == "module2"
            Dictionary Should Not Contain Key    ${response[${I}]}    slash_redirect
            Should Be Equal As Integers   ${response[${I}]['priority']}        2
            Should Be Equal As Strings    ${response[${I}]['host']}            foo.example.org
            Should Be Equal As Strings    ${response[${I}]['url']}             http://127.0.0.0:2000
            Should Be Equal As Strings    ${response[${I}]['lets_encrypt']}    True
            Should Be Equal As Strings    ${response[${I}]['http2https']}      True
            Should Be Equal As Strings    ${response[${I}]['skip_cert_verify']}  True
            Should Be Equal As Strings    ${response[${I}]['user_created']}    False
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-foo-add']}    foo
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-bar-remove']}    ${EMPTY}
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-bar-add']}    bar
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-foo-remove']}    ${EMPTY}
        ELSE IF        $response[$I]['instance'] == "module3"
            Should Be Equal As Strings    ${response[${I}]['slash_redirect']}  False
            Should Be Equal As Integers   ${response[${I}]['priority']}        3
            Should Be Equal As Strings    ${response[${I}]['path']}            /bar
            Should Be Equal As Strings    ${response[${I}]['host']}            bar.example.org
            Should Be Equal As Strings    ${response[${I}]['url']}             http://127.0.0.0:2000
            Should Be Equal As Strings    ${response[${I}]['lets_encrypt']}    True
            Should Be Equal As Strings    ${response[${I}]['http2https']}      True
            Should Be Equal As Strings    ${response[${I}]['skip_cert_verify']}  True
            Should Be Equal As Strings    ${response[${I}]['strip_prefix']}    False
            Should Be Equal As Strings    ${response[${I}]['user_created']}    True
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-foo-add']}    foo
            Should Be Equal As Strings    ${response[${I}]['headers']['request']['X-bar-remove']}    ${EMPTY}
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-bar-add']}    bar
            Should Be Equal As Strings    ${response[${I}]['headers']['response']['X-foo-remove']}    ${EMPTY}
        ELSE IF        $response[$I]['instance'] == "module5"
            Should Be Equal As Strings    ${response[${I}]['forward_auth']['address']}    http://127.0.0.1:9311/api/module/module1/http-basic/add-module1
            Should Be Equal As Strings    ${response[${I}]['forward_auth']['skip_tls_verify']}    True
            Should Be Equal As Strings    ${response[${I}]['forward_auth']['auth_response_headers'][0]}    X-Auth-User
        ELSE
            Fail    Unexpected HTTP route ${response[${I}]['instance']}
        END
    END

Delete routes
    Run task    module/${MID}/delete-route   	 {"instance": "module1"}
    Run task    module/${MID}/delete-route   	 {"instance": "module2"}
    Run task    module/${MID}/delete-route   	 {"instance": "module3"}
    Run task    module/${MID}/delete-route   	 {"instance": "module5"}

Expect initial routes list
    ${response} =  Run task    module/${MID}/list-routes    null    decode_json=${False}
    Should Be Equal As Strings    ${response}    ["cluster-admin"]
