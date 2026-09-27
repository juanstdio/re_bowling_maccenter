# BOL Controlador — parte 2

Controlador Python/Tkinter para simular sensores de pinos a través del puerto serie virtual COM2. Incluye los controles COM1 de la GUI anterior. Se ejecuta en Windows, fuera de la VM, sin paquetes pip obligatorios. Abrir **ABRIR_CONTROLADOR.cmd** (requiere Python 3 con Tkinter).

**Es un emulador experimental del protocolo, no una emulación completa de la máquina.** Se verificaron la GUI y los bytes con clientes TCP locales. Todavía no se ha verificado que BOL.EXE muestre las tiradas en VirtualBox. No desbloquea por sí solo la pantalla inicial: BOL debe haber entrado en una partida y estar esperando una bola. Que #95173 abra configuración solo confirma el teclado.

## Conectar

1. Cerrar serverbolos.py, la GUI anterior y cualquier servidor que use 5000/5001. Esta aplicación sustituye a la anterior y atiende ambos puertos.
2. Con la VM apagada, conservar COM1 como TCP cliente a **127.0.0.1:5000**, puerto invitado **0x3F8, IRQ4**.
3. Habilitar COM2 como TCP cliente a **127.0.0.1:5001**, puerto invitado **0x2F8, IRQ3**. No conectar los dos al mismo socket. Python es el servidor; VirtualBox es el cliente.
4. Abrir ABRIR_CONTROLADOR.cmd y pulsar **Escuchar** en COM1 y COM2 antes de encender la VM.
5. Encender la VM y ejecutar BOL.EXE. La pista predeterminada es 6; se puede leer del INI. Salir de la configuración técnica para probar el juego.
6. En la pestaña Central, consultar estado. La DEMO experimental permite intentar crear la sesión y los nombres, con espera de respuestas. Si COM1 continúa sin responder, guardar el log: este controlador no resuelve por sí mismo ese problema pendiente.
7. En Tiradas, comprobar que aumenta el contador **sondeos**. La conexión TCP por sí sola no basta. El respondedor COM2 se activa automáticamente; no hace falta marcar una casilla.

Los dos sockets son locales al mismo Windows que ejecuta VirtualBox. No es un servicio de acceso por Internet. BOL configura internamente COM1 9600 8N2 y COM2 19200 8N2; GLINK.CFG no determina esos parámetros de BOL.

## Ejemplo: caen 5 pinos

Con una partida ya visible, un rack nuevo en BOL y sondeos COM2 activos:

1. Pulsar **Nuevo rack** para sincronizar el modelo local con ese rack nuevo.
2. Pulsar **5 pinos**: selecciona los primeros cinco disponibles. También se pueden marcar pinos individuales en el triángulo.
3. Pulsar **Enviar tirada** una vez.
4. Esperar las fases reposo → inicio → lectura → retorno. Por defecto cada fase se mantiene al menos 1 segundo y se sirve en al menos dos consultas de BOL.
5. Comprobar en la VM si aparecen los cinco pinos y el puntaje. El texto «secuencia servida» solo informa del intercambio del controlador; NO certifica que el juego haya puntuado.

Para una segunda bola, marcar únicamente los pinos nuevos que caen. Los anteriores se conservan en el estado acumulado de sensores. **Todos restantes** selecciona los disponibles; **0 pinos** limpia la selección para intentar una bola sin nuevos derribos. Los botones de selección no transmiten hasta pulsar Enviar tirada.

Usar **Nuevo rack** cuando BOL realmente haya colocado diez pinos para el siguiente jugador/frame o bola extra. El controlador no conoce el turno ni decide automáticamente las reglas del décimo frame. Nuevo rack limpia los sensores locales; no reinicia la partida ni cambia el turno del programa DOS.

Los números identifican los registros 1..10 del juego, vinculados a las máscaras leídas del ejecutable. La correspondencia con el cableado de una placa física no se ha probado.

## Diagnóstico

- **Sin sondeos COM2:** el botón no inicia tiradas. Revisar el segundo puerto y si BOL está consultando la placa. COM1 conectado no demuestra COM2 funcionando.
- **Sondeos activos, pantalla inicial:** primero falta activar el juego por COM1; transmitir sensores no equivale a iniciar una partida.
- **Secuencia enviada, marcador sin cambios:** conservar el log y anotar la pantalla exacta, pinos seleccionados y fase. Puede faltar otra condición interna o una respuesta de maquinaria. Probar un tiempo mayor por fase permite investigar temporización; no garantiza resolverlo.
- **Caídos locales distintos de la VM:** detener las pruebas y sincronizar al siguiente rack conocido. El controlador no recibe un ACK de puntuación ni puede deducir el turno.
- **Cancelar ciclo:** desactiva el evento en las siguientes respuestas; no revierte una bola que BOL ya haya contabilizado. Las respuestas ya encoladas pueden terminar de enviarse. Detener COM2 corta el enlace.
- **Desconexión:** se cancela el ciclo y se exige un nuevo sondeo antes de otra tirada. Se conserva la selección acumulada para evitar suponer un rearme del juego.

El log completo se guarda automáticamente en `logs/`. Enviar ese archivo junto con lo observado en pantalla. No conectar este laboratorio a maquinaria real.

## Qué se envía

No se envía el número ASCII «5». Se contestan los paquetes de sondeo COM2 con una trama de 15 bytes: `1B 91 [11 bytes de estado] checksum 04`. Los bits de sensores representan los pinos seleccionados. Las señales de inicio y lectura cambian entre fases. Los saludos A5 identificados también reciben respuesta.

En ausencia de consultas no se emiten ráfagas espontáneas. La duración mínima y las dos muestras son decisiones de prueba, no tiempos recuperados de una placa original. Si se detienen los sondeos el ciclo no avanza; Cancelar ciclo permite abandonarlo.

Ver **EVIDENCIA_TIRADAS.md** para el fundamento y límites. `GUI_ANTERIOR.md` y `NOTAS_TECNICAS_PREVIAS.md` se conservan como antecedentes; sus limitaciones del antiguo respondedor describen la versión anterior. Para ejecutar esta versión usar siempre ABRIR_CONTROLADOR.cmd.

## Pruebas incluidas

Ejecutar **PROBAR.cmd**: 12 pruebas de protocolo, sensores, secuencia y TCP. No requieren la VM. `VALIDACION.txt` detalla las verificaciones hechas al crear el ZIP. Ninguna de ellas reemplaza la prueba con BOL.EXE.
