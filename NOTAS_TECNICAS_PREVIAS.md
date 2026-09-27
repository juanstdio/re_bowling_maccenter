# Evidencia de ingeniería inversa y límites

Binario: BOLICHE\BOL.EXE, 449820 bytes, versión textual 3.0.0.1.3.

SHA-256: `ead78b5415bd5d87ecd8607a96d30e0fa275a5c60e7729fa6f8cf4944adfeac1`

No se ejecutó el binario. Se extrajo su primer objeto LE y se desensambló como código x86 de 32 bits usando DUMPBIN. Los offsets siguientes son **relativos al objeto de código**, no direcciones absolutas de ejecución. En este archivo el objeto empieza en offset de archivo `0x1DE00`; por tanto `offset_archivo = 0x1DE00 + offset_codigo`. Los offsets de datos son relativos al objeto de datos y no incluyen reubicaciones del cargador. Las tablas de saltos/datos intercalados no deben interpretarse como instrucciones.

## COM1: recepción y checksum

Rutina de interrupción en `0x2630`; parser relevante en `0x2666–0x270A`.

```text
1B  (20 + número_de_pista)  comando  datos...  checksum  04
```

- `1B` reinicia el índice y la suma acumulada.
- Todos los bytes entre `1B` y `04`, incluido el checksum, se suman.
- Acepta el paquete si `suma & 0x7F == 0` y el segundo byte equivale a `0x20 + Numero desta pista`.
- Los bytes 1B y 04 son delimitadores; no se identificó escape dentro de datos.
- Cálculo usado por el propio emisor, `0x478B–0x47DB`: `checksum = ((-sum(cuerpo)) & 0x7F) | 0x80`.
- El buffer completo pasa al despachador `0x398C`; el comando está en offset de datos `0xB6A2`.

La inicialización de UART está en `0x6BC–0x6E7` y la rutina que calcula divisor y formato en `0x3414–0x34BE`. COM1 recibe 9600, sin paridad, 2 bits de parada y 8 bits de datos. COM2 recibe 19200 con el mismo formato. Esto se obtiene de las instrucciones y parámetros, no del INI de GLINK.

## Comandos COM1 identificados

| Comando | Respuesta | Efecto observado en instrucciones |
|---|---|---|
| 80 | C1 con dato ASCII 2 | Consulta de identificación/tipo; significado exacto de «2» no resuelto. |
| 81 | C3 o FC/D6/EC/C6 | Consulta cuyo resultado depende de banderas internas. |
| C0 | C2 | Pone variable de estado `datos:1AF18` en 2 (`0x3A2E`). |
| 82 | C4 | Pone estado 1 (`0x3A66`); procesa 8 bytes ASCII (`0x48BD`). No reenviar automáticamente: posee lógica para recepción repetida. |
| 86 | C7 | Pone estado 0 (`0x3ACD`). |
| 8A | DA | Lee opciones desde índices 3, 4 y 6 de la trama; tiempo visible, tecla manual y fotocélula, según sus consumidores. No usado en la demo. |
| 8C | DC | Copia hasta 9 caracteres para el equipo (`0x49AF`). |
| 8D..96 | DD..E6 | Carga jugadores 1..10 y campo decimal final. Primer jugador: `0x49F4–0x4AA1`. |
| 97 | E7 | Activa bandera de fin de nombres `datos:1AF1C` (`0x3BF9`). |

La respuesta se transmite antes de algunos efectos secundarios (`0x4870` y siguientes). Por eso un ACK no confirma dibujo ni finalización.

Estado 2 es consumido por el bucle principal en `0xAC4–0xB18`, que llama a `0x52A6`; esa rutina contiene el flujo de entrenamiento, con dibujo posterior a los intentos de diálogo COM2 (`0x53EA–0x540F`). Estado 1 sigue `0xB22` y termina entrando en la rutina del juego `0x195F3`. La espera de nombres y su finalización están en `0x19788–0x19804`.

## Campos del comando 82

El parser lee:

| Índices de trama (desde 0) | Conversión | Variable de datos |
|---|---|---|
| 3..5 | Tres dígitos ASCII | 1B040 |
| 6..8 | Tres dígitos ASCII | 1B044 |
| 9 | Un dígito ASCII | 1B048 |
| 10 | Un dígito ASCII | 1B050 |

La modalidad almacenada en 1B050 tiene ramas para 1, 2 y 3. Los usos posteriores relacionan 1B044 con cantidad de líneas y 1B040 con el dato que retorna la consulta de partida. El tercer campo sigue sin semántica confirmada. La demo usa `00101003` como caso inicial de investigación, no como captura de un servidor real.

Para nombres, se envían 9 caracteres rellenados con espacios más `000` como campo final. El primer jugador se analiza buscando el final de trama tres posiciones después y calcula un decimal de tres dígitos. El texto de interfaz y los archivos de partida contienen handicap; no se validó visualmente este campo.

## COM2: placa de maquinaria

- Transmisión de estado hacia la placa en `0x34C1–0x374F`, paquete de 11 bytes: `1B 81 ... checksum 04`.
- Recepción de estado en `0x3760–0x386A`: acepta segundo byte `91`, checksum módulo 128, almacena 15 bytes en `datos:B670`.
- Negociación corta en `0x386B–0x3961`: segundo byte A5; códigos 81, 82 y 83 activan distintas banderas. Al iniciar, BOL.EXE transmite `1B A5 82 D9 04`; durante operación también transmite `1B A5 81 DA 04`.
- `placa_com2.py` responde con esos dos códigos cuando los recibe, y emite 15 bytes de estado a las consultas. Está diseñado para probar aceptación del parser; no representa una placa real completa.

Bits relevantes de la trama de 15 bytes, numerada desde 0:

- Bytes 2 y 3: usados por las rutinas que contabilizan sensores de pinos. En orden de análisis se consultan máscaras `byte2:10, byte2:08, byte3:02, byte2:02, byte3:01, byte3:08, byte2:01, byte2:04, byte3:04, byte3:10`. No se certificó la correspondencia física de cada sensor.
- Byte 3, bit 20: participa en la secuencia de estados de una tirada (`0x19E6E` y `0x19EAF`).
- Byte 5, bit 01: participa en el disparo de procesamiento de la jugada y en entrenamiento (`0x19E91`, `0x576D`).
- Byte 5, bits 02 y 08, y byte 6, bits 01 y 02: usados en banderas adicionales; requieren más trazado y prueba.

Para emular puntuaciones no alcanza con enviar un total numérico: hay que reproducir una secuencia coherente de sensores y eventos. Esa parte queda pendiente de la captura de respuestas y cambios de pantalla en la VM. No se incluyó un comando «strike» inventado ni un parche al EXE.

## Verificación del paquete

Las pruebas offline incluyen dos paquetes constantes observados literalmente en el ejecutable, checksum incorrecto, reensamblado de tráfico TCP, descarte de dirección ajena y una conexión cliente-servidor local. Prueban la implementación del laboratorio; no equivalen a emular el procesador DOS ni a ejecutar BOL.EXE.

Referencia de formato del binario: [documentación de ejecutables lineales de Open Watcom](https://www.openwatcom.org/ftp/manuals/current/pguide.pdf). El archivo `evidencia_ensamblador.txt` conserva extractos relevantes del análisis local.
