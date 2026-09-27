# BOL GUI v2 — Python escucha, VirtualBox se conecta

La aplicación ofrece una GUI en Tkinter, sin paquetes externos obligatorios. Se ejecuta en el anfitrión, fuera de DOS. Python debe incluir Tkinter (habitual en la instalación de Python para Windows).

## Empezar con la conexión que ya funcionaba

1. Cerrar `serverbolos.py`, `central.py` y otros procesos que usen el puerto 5000. Esta GUI los sustituye; no es un cliente de `serverbolos.py`.
2. Con la VM apagada, abrir `ABRIR_GUI.cmd`, o ejecutar `python bolos_gui.py`.
3. Dejar dirección `127.0.0.1`, puerto COM1 `5000`, pista `6` y pausa `5` ms por byte. Pulsar **Escuchar** en COM1.
4. En VirtualBox mantener la conexión **TCP cliente hacia 127.0.0.1:5000**. El puerto invitado debe ser COM1, dirección 0x3F8, IRQ 4. Aquí Python es el servidor. Si VirtualBox estaba como servidor, cambiar el sentido para que coincida con esta GUI.
5. Encender la VM. La GUI indicará **TCP conectado · BOL no verificado**.
6. Dentro de DOS, ejecutar **BOL.EXE** y esperar a la pantalla inicial. Salir de configuración técnica antes de probar órdenes del juego. No ejecutar GLINK para estas pruebas.
7. Pulsar **Consultar estado**. La GUI registra lo enviado y TODO byte recibido. Solo una respuesta con checksum, dirección y código esperado cambia el estado a **Respuesta BOL compatible recibida**.
8. Si la consulta responde, probar **Entrenamiento**. La DEMO de nombres es experimental y modifica la sesión/partida dentro de la VM: usar una copia o snapshot.

El número de pista se puede leer de BOLICHE.INI o GLINK.CFG con el botón correspondiente. Solo se lee; no modifica los archivos. Se prioriza `Numero desta pista` en el INI. El puerto TCP 5000 no es el número de pista ni el valor `Porta Serial=1`.

## Qué corrige esta versión

El archivo central.log.txt muestra repetidos errores 10061: la versión anterior intentaba ser cliente TCP cuando no había servidor escuchando. La conexión que sí funciona en el log de serverbolos.py tiene el sentido contrario: **VirtualBox conecta a Python**.

Además, ejecutar central.py contra serverbolos.py no crea automáticamente un puente a la VM. Ese servidor atiende una conexión a la vez; un segundo cliente puede quedar pendiente sin llegar al extremo serie. Esta GUI se conecta directamente con VirtualBox mediante su socket aceptado.

La GUI:

- Escucha antes de arrancar la VM y admite reconexión después de desconectarse.
- Distingue conexión TCP, bytes RX y respuestas compatibles con BOL.
- Calcula cabecera, dirección y checksum de los comandos con botones.
- Agrega una pausa configurable entre bytes COM1 (5 ms por defecto), útil para comprobar si la UART virtual pierde ráfagas. Es una hipótesis de diagnóstico, no una causa demostrada del silencio.
- Detiene la DEMO cuando falta un ACK y no reenvía automáticamente comandos que cambian estado.
- Mantiene la ventana operativa durante la espera de red. Los hilos de red no manipulan Tkinter.
- Guarda logs automáticamente y permite exportarlos.

## Lo que muestran los logs recibidos

No hay bytes RX en el fragmento de consola enviado. Por tanto, todavía no se comprobó que BOL.EXE esté recibiendo los paquetes ni respondiendo. La conexión TCP al encender la VM la establece VirtualBox; no demuestra que el programa DOS haya abierto la UART.

Las tramas `1B 26 C0 9A 04` y `1B 26 81 D9 04` concuerdan con el parser analizado para pista 6. No hay evidencia en esos logs para cambiar su checksum.

Dos envíos del log sí tienen problemas de formato/destino:

- `80 A0 80 ...` son datos de estado COM2 sin cabecera/checksum/terminador. No son un comando COM1 válido. La pestaña de placa construye el paquete completo cuando recibe una consulta.
- La trama de inicio que termina en `00` está incompleta para este parser: el terminador es `04`. La línea siguiente del log corrige ese byte, pero no registra respuesta.

El servidor adjunto interpreta GLINK como un protocolo de longitud y checksum diferente. No reutilizamos ese decodificador para BOL.EXE. Su función de envío hexadecimal podía transmitir los bytes tal cual, por lo que esa diferencia por sí sola tampoco explica la ausencia total de RX. No se ha auditado ni validado aquí su implementación del protocolo GLINK.

## Si sigue sin responder

1. Confirmar COM1 invitado **0x3F8, IRQ4**, no solo el puerto TCP 5000. Verificar que está ejecutándose BOL.EXE, en la pantalla inicial y con pista 6.
2. Probar **Consultar estado** con pausa 5 ms; si no hay respuesta, probar 10 ms y guardar ambos registros. No hacer envíos masivos ni repetir inicio de partida para diagnosticar el enlace.
3. No usar simultáneamente el servidor antiguo y esta GUI, ni conectar central.py a esta GUI como si fuera la VM.
4. Si se ven RX pero no una respuesta válida, compartir esos bytes. Si RX sigue en cero, compartir el log de la GUI y una captura de la configuración de puertos serie de VirtualBox.
5. Revisar qué pantalla está abierta en DOS. Una pantalla modal puede no procesar los cambios del juego de la misma manera; la prueba inicial debe hacerse sobre el BMP/inicio.

No se presupone que COM2 resuelva el silencio de COM1. Son dos enlaces diferentes.

## COM2 opcional: respondedor experimental de placa

Con la VM apagada, habilitar COM2 como TCP cliente hacia **127.0.0.1:5001**, dirección invitada **0x2F8, IRQ3**. En la GUI pulsar Escuchar en COM2 antes de encender la VM.

En la pestaña Placa, marcar **Responder automáticamente** y aplicar los 11 bytes de estado por defecto. Los mensajes se generan en respuesta a las consultas; no se envía el bloque suelto al puerto COM1.

El respondedor reconoce el saludo A5 y los sondeos de estado con cabecera 81, y emite respuestas con cabecera 91. El estado es sintético. **No emula todas las transiciones de máquina, tiros o puntuaciones**, y puede no bastar para salir de las esperas de rearme. Se incluye para observar y probar el segundo enlace.

BOL.EXE configura COM1 a 9600 8N2 y COM2 a 19200 8N2 en las instrucciones analizadas. `Taxa de Comunicacao=115` pertenece a GLINK.CFG. El TCP crudo transporta bytes; no transmite controles RTS/DTR ni negocia baudrate.

## DEMO y envío manual

DEMO envía consulta, comando 82 con datos `00101003`, equipo 8C, jugadores 8D..96 y fin de nombres 97. Esa secuencia proviene del análisis previo y sigue pendiente de verificación visual con BOL.EXE. Los nombres son ASCII de hasta 9 caracteres. Un ACK no significa que el marcador ya esté listo.

La pestaña Trama manual acepta paquetes completos BOL con checksum válido. Rechaza bloques sueltos y el terminador 00. No es una consola de transferencia de archivos GLINK.

Cancelar secuencia detiene las siguientes órdenes y la espera del ACK; no revierte lo enviado ni interrumpe un paquete que ya está transmitiéndose. Detener el puerto cierra el enlace.

## Pruebas y alcance

Ejecutar `PROBAR.cmd` o `python pruebas.py`. Se prueba el servidor con un cliente TCP local que representa a VirtualBox: envío con pausa, recepción fragmentada, rechazo de checksum, reconexión y respuesta COM2. También se verifica la lectura del INI antiguo con sección vacía.

Estas pruebas no ejecutan BOL.EXE. El detalle de las verificaciones realizadas al preparar el ZIP está en VALIDACION.txt. El análisis previo está en NOTAS_TECNICAS_PREVIAS.md y evidencia_ensamblador.txt.

La GUI no modifica los originales, no inicia la VM ni requiere que la pista física esté conectada. No usar las pruebas de estado en maquinaria real.
