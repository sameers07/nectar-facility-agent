# Troubleshooting FAQs

## Why would a building's temperature be high even if the chiller is running?

A chiller reporting "running" status is not the same as the loop
delivering full cooling capacity. If an AHU on the same loop has reduced
airflow (see AHU Troubleshooting Guide), less conditioned air reaches the
space even though the chiller is operating normally, which raises the
building temperature and can also raise the chiller's power deviation as
it works harder for the same result.

## What does a LOW_AIRFLOW alert mean in practice?

It means the AHU's measured airflow has dropped below its acceptable
threshold, most commonly due to filter clogging. It does not by itself
mean the fan or motor has failed -- check filters before assuming a
mechanical fault.

## Is elevated chiller power deviation always a chiller problem?

No. It is frequently a downstream symptom of restricted airflow elsewhere
in the same loop. Check for AHU alerts on the same loop before assuming
the chiller itself needs service.

## What should I check if AHU airflow is low?

Check filters first, then dampers, then the belt drive, then the fan
motor -- in that order. See the AHU Troubleshooting Guide for the full
procedure.
