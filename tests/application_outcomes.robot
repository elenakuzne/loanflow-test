*** Settings ***
Documentation    Decision-outcome coverage for the Application API.
...              Each row drives the same flow: submit → check status → verify notification.
...              Outcome is determined by income-to-loan ratio — add a new row for a new scenario.
Resource     ../resources/api.resource
Variables    ../resources/variables.py
Suite Setup    Start Test Environment
Suite Teardown    Stop Test Environment
Test Setup    Reset Test Environment
Test Template    Application Decision Should Be

*** Test Cases ***                               NAME                  INCOME    AMOUNT    EMPLOYMENT      EXP STATUS
Approve strong application                       Approve Case          90000     20000     employed        approved
Queue borderline application for manual review   Manual Review Case    60000     20000     employed        pending
Reject low income application                    Low Score Case        30000     20000     employed        rejected
Reject unemployed applicant with high amount     Unemployed Case       50000     15000     unemployed      rejected

*** Keywords ***
Application Decision Should Be
    [Arguments]    ${name}    ${income}    ${amount}    ${employment}    ${exp_status}
    ${payload}=    Build Application Payload
    ...    applicant_name=${name}
    ...    annual_income=${income}
    ...    requested_amount=${amount}
    ...    employment_status=${employment}
    ${response}=    Post Application    ${payload}
    Response Status Should Be    ${response}    201
    ${body}=    Response Json    ${response}
    Dictionary Should Contain Item    ${body}    status    ${exp_status}
    ${id}=    Get From Dictionary    ${body}    id
    Notification Should Exist    ${id}    ${exp_status}
