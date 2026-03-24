*** Settings ***
Library    Collections
Library    RequestsLibrary
Library    ../libraries/LoanFlowLibrary.py

*** Variables ***
${API_SESSION}    loanflow
${BASE_URL}       ${EMPTY}

*** Keywords ***
Start Test Environment
    ${base_url}=    Start Loanflow Api
    Set Suite Variable    ${BASE_URL}    ${base_url}
    Create Session    ${API_SESSION}    ${base_url}

Reset Test Environment
    Reset Loanflow State
    Delete All Sessions
    Create Session    ${API_SESSION}    ${BASE_URL}

Stop Test Environment
    Stop Loanflow Api

Post Application
    [Arguments]    ${payload}
    ${response}=    POST On Session    ${API_SESSION}    /api/v1/applications    json=${payload}    expected_status=anything
    RETURN    ${response}

Get Application
    [Arguments]    ${application_id}
    ${response}=    GET On Session    ${API_SESSION}    /api/v1/applications/${application_id}    expected_status=anything
    RETURN    ${response}

List Applications
    [Arguments]    ${status_filter}=${EMPTY}
    IF    "${status_filter}" == ""
        ${response}=    GET On Session    ${API_SESSION}    /api/v1/applications    expected_status=anything
    ELSE
        ${params}=    Create Dictionary    status=${status_filter}
        ${response}=    GET On Session    ${API_SESSION}    /api/v1/applications    params=${params}    expected_status=anything
    END
    RETURN    ${response}

Response Status Should Be
    [Arguments]    ${response}    ${expected_status}
    Should Be Equal As Integers    ${response.status_code}    ${expected_status}

Response Json
    [Arguments]    ${response}
    ${body}=    Evaluate    $response.json()
    RETURN    ${body}

