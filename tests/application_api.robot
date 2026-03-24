*** Settings ***
Documentation    Structural API behaviour: validation, idempotency, error handling, and retrieval.
...              These tests cover flows that are too structurally different to fit the outcomes template.
Resource     ../resources/api.resource
Variables    ../resources/variables.py
Suite Setup    Start Test Environment
Suite Teardown    Stop Test Environment
Test Setup    Reset Test Environment

*** Test Cases ***
Reject a request that violates validation rules
    [Tags]    negative    validation    api
    ${payload}=    Build Application Payload
    ...    applicant_name=Validation Case
    ...    annual_income=45000
    ...    requested_amount=${MIN_LOAN_AMOUNT - 1}
    ...    employment_status=employed
    ${response}=    Post Application    ${payload}
    Response Status Should Be    ${response}    400
    ${body}=    Response Json    ${response}
    Dictionary Should Contain Item    ${body}    error_code    VALIDATION_ERROR
    ${details}=    Get From Dictionary    ${body}    details
    ${details_text}=    Evaluate    " ".join($details)
    Should Contain    ${details_text}    requested_amount

Reject unsupported employment status
    [Tags]    negative    validation    api
    ${payload}=    Build Application Payload
    ...    applicant_name=Employment Validation
    ...    annual_income=45000
    ...    requested_amount=15000
    ...    employment_status=contractor
    ${response}=    Post Application    ${payload}
    Response Status Should Be    ${response}    400
    ${body}=    Response Json    ${response}
    Dictionary Should Contain Item    ${body}    error_code    VALIDATION_ERROR
    ${details}=    Get From Dictionary    ${body}    details
    ${details_text}=    Evaluate    " ".join($details)
    Should Contain    ${details_text}    employment_status

Persist error status when Risk Engine times out
    [Tags]    resilience    api
    Configure Risk Engine Delay    6
    ${payload}=    Build Application Payload
    ...    applicant_name=Timeout Case
    ...    annual_income=70000
    ...    requested_amount=15000
    ...    employment_status=self_employed
    ${response}=    Post Application    ${payload}
    Response Status Should Be    ${response}    201
    ${body}=    Response Json    ${response}
    Dictionary Should Contain Item    ${body}    status    error
    Dictionary Should Contain Item    ${body}    risk_score    ${None}

Return 503 when the Risk Engine is unavailable
    [Tags]    negative    resilience    api
    Stop Risk Engine
    ${payload}=    Build Application Payload
    ...    applicant_name=Unavailable Case
    ...    annual_income=60000
    ...    requested_amount=20000
    ...    employment_status=employed
    ${response}=    Post Application    ${payload}
    Response Status Should Be    ${response}    503
    ${body}=    Response Json    ${response}
    Dictionary Should Contain Item    ${body}    error_code    RISK_ENGINE_UNAVAILABLE

Return the existing application when the same request is repeated
    [Tags]    regression    idempotency    api
    ${payload}=    Build Application Payload
    ...    applicant_name=Duplicate Case
    ...    annual_income=60000
    ...    requested_amount=20000
    ...    employment_status=employed
    ${first_response}=    Post Application    ${payload}
    ${second_response}=    Post Application    ${payload}
    Response Status Should Be    ${first_response}    201
    Response Status Should Be    ${second_response}    200
    ${first_id}=    Get From Dictionary    ${first_response.json()}    id
    ${second_id}=    Get From Dictionary    ${second_response.json()}    id
    Should Be Equal    ${first_id}    ${second_id}
    ${list_response}=    List Applications
    Response Status Should Be    ${list_response}    200
    ${applications}=    Response Json    ${list_response}
    Length Should Be    ${applications}    1

Rejected applications are retrievable by ID and filterable by status
    [Tags]    retrieval    api
    ${payload}=    Build Application Payload
    ...    applicant_name=Retrieval Case
    ...    annual_income=50000
    ...    requested_amount=15000
    ...    employment_status=unemployed
    ${create_response}=    Post Application    ${payload}
    Response Status Should Be    ${create_response}    201
    ${id}=    Get From Dictionary    ${create_response.json()}    id
    ${fetched_response}=    Get Application    ${id}
    Response Status Should Be    ${fetched_response}    200
    ${fetched}=    Response Json    ${fetched_response}
    Dictionary Should Contain Item    ${fetched}    applicant_name    Retrieval Case
    ${filtered_response}=    List Applications    rejected
    Response Status Should Be    ${filtered_response}    200
    ${filtered}=    Response Json    ${filtered_response}
    Length Should Be    ${filtered}    1
