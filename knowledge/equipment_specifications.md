# Equipment Specifications

## Chiller units

Chiller-01 and Chiller-02 are water-cooled centrifugal chillers, rated
baseline power draw calibrated per-unit at commissioning. Power deviation
is measured against that per-unit baseline, not a fleet average.

## AHU units

AHU-01, AHU-02, and AHU-03 are variable-air-volume units with belt-driven
supply fans. Design airflow is rated at 100% for each unit; the airflow
percentage reported by the monitoring system is relative to that design
value, so an airflow reading of 41% means the unit is moving 41% of its
rated design airflow.

## Alert types

- `LOW_AIRFLOW`: airflow has dropped below the unit's acceptable operating
  threshold.
- Severity `high` on any alert means it should be treated as an active
  fault requiring investigation, not a routine notice.
