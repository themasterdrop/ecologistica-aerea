# Batería de pruebas — Asistente IA (qwen-ecologistica:14b) sobre EcoLogisticaDB

Pregúntalas tal cual en el Asistente. En cada una se indica **qué verificar** (columnas / cadenas de JOIN correctas) para puntuarla. Pensadas para resistir el escrutinio de un profesor de ingeniería de datos.

> Tip de evaluación: marca PASS solo si (a) ejecuta sin error y (b) usa la tabla/columna/cadena correcta indicada. Una consulta que "devuelve algo" pero con la columna equivocada NO es PASS.

---

## A. Sanidad básica (deben pasar sin problema)

1. ¿Cuántos vuelos hay en total? → `COUNT(*)` desde `VUELO`.
2. ¿Cuántos vuelos fueron cancelados? → `RESULTADO`, `WHERE R.Cancelled = 1`.
3. Emisiones totales de CO2 en kg. → `SUM(R.co2)` desde `RESULTADO` (co2 está en RESULTADO).
4. Consumo de combustible promedio por vuelo. → `AVG(R.fuel_burn)` (libras, en RESULTADO).

## B. Las que estaban rotas — deben demostrar la corrección

5. Top 10 modelos de avión por número de vuelos. → `MA.Fabricante`, `MA.Modelo`, `JOIN MODELO_DE_AVION MA ON AN.acft_icao = MA.acft_icao` (NO `ID_Modelo`, NO `Manufacturer/Model`).
6. ¿Cuántos vuelos operó cada fabricante de avión? → `MA.Fabricante` vía `AN.acft_icao = MA.acft_icao`.
7. Top 10 ciudades de destino por número de vuelos. → `CI.CityName` (NO `Nombre_Ciudad`).
8. ¿Qué modelos de avión opera cada aerolínea? → `MA.Fabricante`, `MA.Modelo` + `AEROLINEA` por `DOT_ID_Operating_Airline`.

## C. Columnas-trampa (lo que el profesor probará)

9. Retraso de llegada promedio de todos los vuelos. → `AVG(DR.ArrDelayMinutes)` (NUNCA `ArrDelay` a secas).
10. ¿Cuántos vuelos llegaron con 15 minutos o más de retraso? → `DR.ArrDel15 = 1` **o** `DR.ArrDelayMinutes >= 15` (ambas válidas).
11. Distancia total volada. → `SUM(RU.Distance)` vía `PROGRAMACION → RUTA` (NUNCA `R.Distance` ni `V.Distance`).
12. ¿Cuál es el aeropuerto de destino más alto? → `AD.Elevacion_ft` (exactamente `Elevacion_ft`, no `Elevacion`, no `Elevation`).
13. Nombre del aeropuerto con más vuelos de salida. → `AO.Nombre_Aeropuerto` (NO `Name`, NO `AirportName`).
14. Retraso de llegada promedio por aerolínea. → `AL.Operating_Airline` (NO `AirlineName`).
15. Número de vuelos por estado de destino. → `E.StateName` (NO `Nombre_Estado`).

## D. Cadenas de JOIN difíciles (las que rompen a los modelos)

16. Tiempo de taxi out promedio por aeropuerto de origen. → cadena `VUELO → RESULTADO → CRONOMETRIA_REAL → TAXI` (`TX.TaxiOut`); TAXI nunca directo a VUELO.
17. Distancia promedio por grupo de distancia. → `RU.Distance`, `RU.DistanceGroup` vía PROGRAMACION→RUTA.
18. Número de vuelos por continente de destino. → cadena geográfica completa `AEROPUERTO→CIUDAD→ESTADO→WAC→CONTINENTE`, `C.Nombre_Continente`.
19. ¿Cuántos vuelos salieron desde cada continente de origen? → usa `V.OriginAirportID = AO.AirportID` (alias consistente; era el bug que corregimos).
20. Retraso de llegada promedio por grupo de distancia. → combina cadena de DEMORAS **y** de RUTA correctamente.

## E. Combinaciones multi-concepto (generalización)

21. CO2 total y distancia total por aerolínea. → `RESULTADO` (co2) + `PROGRAMACION→RUTA` (Distance) + `AERONAVE→AEROLINEA`, agrupado por `Operating_Airline`.
22. Retraso de llegada promedio por continente de destino. → DEMORAS + geografía completa en una sola consulta.
23. Top 10 modelos de avión por emisiones de CO2 totales. → `MODELO_DE_AVION` + `RESULTADO`, `MA.Fabricante/MA.Modelo` + `SUM(R.co2)`.
24. Emisiones de CO2 por cada 1000 millas voladas. → `SUM(R.co2)/SUM(RU.Distance)` con `NULLIF` para evitar división por cero.

## F. SQL avanzado (lo que pide un profesor de ingeniería de datos)

25. Para cada aerolínea, su retraso de llegada promedio y su ranking. → función de ventana `RANK()/ROW_NUMBER() OVER (ORDER BY AVG(...))`.
26. Numera los vuelos de cada aerolínea por retraso de llegada descendente. → `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)`.
27. Tabla dinámica con el número de vuelos por continente de destino en columnas. → `PIVOT (... FOR Nombre_Continente IN ([Norteamerica],...))`.
28. Con un CTE, aerolíneas cuyo retraso promedio supera el promedio global. → `WITH ... AS (...)` + subconsulta de promedio.
29. Crea un stored procedure que reciba un código IATA y devuelva número de vuelos y CO2 total. → `CREATE OR ALTER PROCEDURE ... @IATA ...`.
30. Crea una vista con resumen por aerolínea: vuelos, CO2 total y combustible total. → `CREATE OR ALTER VIEW ...`.

## G. Adversariales / honestidad (las trampas finales)

31. Desglosa el retraso total por causa (clima, aerolínea, seguridad). → **Trampa:** esas columnas (`WeatherDelay`, `CarrierDelay`, etc.) **NO existen** en tu DB. Lo ideal: que NO invente esas columnas; que use lo disponible (`ArrDelayMinutes`/`DepDelayMinutes`) o indique que no hay ese dato. (Esta es la que más cuesta — vale oro si la pasa.)
32. ¿Cuántas aeronaves distintas usa cada aerolínea? → `COUNT(DISTINCT V.Tail_Number)`, no confundir aeronave (Tail_Number) con modelo (acft_icao).
33. Distancia promedio de los vuelos cancelados. → debe respetar que `fuel_burn`/`co2` son 0 en cancelados, pero la distancia (RUTA) sigue existiendo; cadena correcta.
34. Top 5 aerolíneas con más vuelos (verifica sintaxis T-SQL). → `SELECT TOP 5 ...` (NO `LIMIT`).

---

## Cómo puntuar (sugerencia)

- **PASS estructural + ejecución**: usa la columna/cadena correcta Y corre sin error.
- Apunta el % en primer intento. Con el set de 07_eval ya viste ~95% / ejecución 20/20.
- Las preguntas de la sección G son las de mayor valor para "blindar" la demo: muestran que el modelo conoce el esquema real y no alucina.

> Si una falla, fíjate si el bucle de autocorrección de `app.py` la arregla en el 2º intento (usa `schema_real`). Una falla que se autocorrige sigue siendo una buena historia para el profesor.
