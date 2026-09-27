# Base del controlador de sensores

Análisis estático de BOL.EXE con SHA256 ead78b5415bd5d87ecd8607a96d30e0fa275a5c60e7729fa6f8cf4944adfeac1. Offsets relativos al objeto de código, como en NOTAS_TECNICAS_PREVIAS.md. Los extractos de esta revisión están en evidencia_tiradas.txt.

## Máquina de estados observada

En 0x19E6E..0x19F0B se consulta la variable de estado datos:1B1EC:

1. Si el bit 0x20 de datos:B673 es cero y el estado era 0, pasa a 1.
2. Si el bit 0x01 de datos:B675 es uno y el estado es 1, pasa a 2.
3. Estado 2 puede entrar en la ruta de procesamiento, sujeto a otras condiciones locales.
4. En 0x1A2F4..0x1A309 se llama condicionalmente a 0x1D8AA (sensores) y se establece estado 3.
5. Si el bit 0x20 vuelve a uno y el estado era 3, vuelve a 0 (0x19EAF..0x19EF4).

Se propone por tanto una secuencia de cuatro fases: reposo (bit20=1/evento=0), inicio (0/0), lectura (0/1), retorno (1/0). Las duraciones y repetición por sondeos son una hipótesis de transporte. No se tiene captura de la placa original ni confirmación de que otras banderas sintéticas sean suficientes.

## Sensores

El paquete recibido se copia a datos:B670 en 0x3801..0x380E. Así, B672 es byte 2 de la trama completa y B675 es byte 5. Los índices siguientes cuentan desde cero e incluyen 1B y 91.

| Registro del pino | Byte trama | Máscara |
|---|---|---|
| 1 | 2 | 10 |
| 2 | 2 | 08 |
| 3 | 3 | 02 |
| 4 | 2 | 02 |
| 5 | 3 | 01 |
| 6 | 3 | 08 |
| 7 | 2 | 01 |
| 8 | 2 | 04 |
| 9 | 3 | 04 |
| 10 | 3 | 10 |

Máscaras en hexadecimal. La rutina 0x1D8AA y bloques siguientes leen esos bits. En el caso de primera bola, por ejemplo 0x1DB06..0x1DB68, el bit activo provoca registrar el pino y sumar un punto si no estaba registrado. Las ramas de bolas siguientes contemplan registros previos. La rutina 0x5F2A usa la misma asociación de registros y máscaras para construir salidas.

El controlador conserva pinos acumulados hasta Nuevo rack; esta política debe contrastarse en la VM, especialmente en la segunda bola y el décimo frame. No implementa un marcador paralelo ni afirma conocer el resultado del juego.

Para pinos 1..5 en la fase lectura, los primeros cuatro bytes de payload son `9A 83 80 81`: máscaras de cinco sensores, inicio activo y evento de lectura. En retorno son `9A A3 80 80`. Se mantiene 0x80 en los bits altos y el resto de campos del estado sintético previo; su semántica completa no está reconstruida.

## Alcance

Una trama enviada correctamente por TCP no acredita que la UART virtual la haya entregado ni que BOL la haya procesado. Tampoco un sondeo COM2 acredita que exista una partida. Los controles están listos para probar las hipótesis con registros de bytes; la compatibilidad visual con la VM sigue pendiente.
