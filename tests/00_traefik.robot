*** Settings ***
Library    SSHLibrary

*** Test Cases ***
Check if traefik service is loaded correctly
    ${output}  ${rc} =    Execute Command    runagent -m ${MID} systemctl --user show --property=LoadState traefik
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    Should Be Equal As Strings    ${output}    LoadState=loaded
