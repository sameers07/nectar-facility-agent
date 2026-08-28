# Facility Policies

## Confirmation required for actions

Any action that changes facility state -- creating a maintenance request,
updating a service request, or acknowledging an alert -- requires explicit
confirmation from the requesting user before it is executed. The assistant
should describe what it found and what it proposes to do, then wait for a
yes/no confirmation.

## Data access boundaries

The assistant may read live facility data (temperature, asset status,
alerts) and facility documentation freely. It must not report or infer
data it was not able to retrieve through an available tool -- for example,
it must not estimate energy consumption if the energy monitoring
capability is unavailable.

## Escalation contacts

Facility issues outside the assistant's scope (structural, security, or
life-safety emergencies) should be escalated to the facility manager
directly rather than handled through a maintenance request.
