# Maintenance Procedures

## Creating a service request

A maintenance/service request should be created when a fault is confirmed
(not merely suspected) and requires a technician on-site to resolve --
for example, a hard chiller fault, an AHU that fails to start after basic
checks, or an alert that persists after the standard troubleshooting steps
have been exhausted. Routine adjustments (e.g. clearing a manual BMS
override) do not require a service request.

## Severity levels

- **High**: active alert with a defined fault code (e.g. LOW_AIRFLOW), or
  any safety interlock trip. Should be actioned within 4 hours.
- **Medium**: performance degradation without an active fault (e.g.
  elevated but not critical power deviation). Should be actioned within
  1 business day.
- **Low**: preventive/scheduled maintenance, no immediate operational
  impact.

## Preventive maintenance schedule

AHU filters: inspect monthly, replace quarterly or when airflow drops
below 90% of design. Chiller condenser coils: clean quarterly. Belt
drives: inspect for wear semi-annually.
