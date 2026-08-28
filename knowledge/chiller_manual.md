# Chiller Manual

## Normal operating range

A chiller in the "running" state should show a power deviation within
+/-10% of its baseline. A sustained deviation above 15% typically
indicates the chiller is working harder than normal to reject the same
heat load, which is frequently caused by a downstream airflow restriction
(e.g. an AHU serving the same loop reporting low airflow) rather than a
fault in the chiller itself.

## Power deviation troubleshooting

If power deviation is elevated: first confirm condenser water flow and
temperature are within spec, then check whether any AHU on the same
chilled water loop has an active low-airflow or fault alert -- reduced
airflow forces the chiller to run longer or harder to hit the same supply
temperature, which shows up as a power deviation even though the chiller
hardware is healthy.

## Refrigerant and compressor faults

A chiller reporting a hard fault (not just elevated power draw) should not
be restarted without inspection. Common fault causes are low refrigerant
charge, condenser fouling, or compressor overload. These require a
qualified technician and a maintenance request should be created rather
than attempting a manual restart.

## Maintenance interval

Chillers should have condenser coils cleaned quarterly and refrigerant
charge verified annually, or sooner if power deviation exceeds 15% for
more than 48 hours.
