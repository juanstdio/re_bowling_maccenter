"""Modelo experimental COM2 inferido de BOL.EXE; no confirma puntuaciones."""
import threading
import time
from protocolo import paquete, valido

# Índices del payload de 11 bytes (trama: +2), orden de registros del juego.
SENSORES = ((0,16),(0,8),(1,2),(0,2),(1,1),
            (1,8),(0,1),(0,4),(1,4),(1,16))

def estado(caidos, fase='reposo'):
    pins = frozenset(caidos)
    if not pins <= set(range(1,11)):
        raise ValueError('Pinos permitidos: 1 a 10.')
    if fase not in ('reposo','inicio','lectura','retorno'):
        raise ValueError('Fase desconocida.')
    b = bytearray([0x80]*11)
    for pin in pins:
        i, mask = SENSORES[pin-1]
        b[i] |= mask
    if fase in ('reposo','retorno'):
        b[1] |= 0x20
    if fase == 'lectura':
        b[3] |= 1
    return bytes(b)

class ControlTiradas:
    """Avanza SOLO cuando BOL consulta; tiempos de laboratorio, ajustables.

    Dos sondeos como mínimo por fase. No existe ACK de puntuación aquí.
    El llamador transmite las respuestas en orden por una sola conexión.
    """
    FASES = ('reposo','inicio','lectura','retorno')
    def __init__(self, reloj=time.monotonic):
        self.reloj = reloj
        self.lock = threading.RLock()
        self.caidos = frozenset()
        self.antes = frozenset()
        self.fase = None
        self.inicio = None
        self.muestras = 0
        self.duracion = 1.0
        self.ultimo_sondeo = None
        self.total_sondeos = 0
        self.aviso = 'Sin sondeos COM2. No se conoce el marcador de BOL.'

    def snapshot(self):
        with self.lock:
            return dict(caidos=sorted(self.caidos), fase=self.fase,
                        muestras=self.muestras, sondeos=self.total_sondeos,
                        ultimo=self.ultimo_sondeo, aviso=self.aviso)

    def lanzar(self, nuevos, duracion=1.0):
        with self.lock:
            nuevos = frozenset(nuevos)
            estado(nuevos)
            if not .25 <= duracion <= 10:
                raise ValueError('Duración por fase: 0.25 a 10 segundos.')
            if self.fase is not None:
                raise ValueError('Hay una secuencia en curso.')
            if self.ultimo_sondeo is None or self.reloj()-self.ultimo_sondeo > 10:
                raise ValueError('Faltan sondeos COM2 recientes de BOL.EXE. Ejecutar el juego y revisar COM2.')
            if nuevos & self.caidos:
                raise ValueError('Se seleccionaron pinos ya caídos. Rearmar solo cuando corresponda en BOL.')
            self.antes = self.caidos
            self.caidos |= nuevos
            self.duracion = duracion
            self.fase = 0
            self.inicio = None
            self.muestras = 0
            self.aviso = f'Secuencia solicitada: {len(nuevos)} nuevos, {len(self.caidos)} acumulados. Sin confirmar en BOL.'

    def cancelar(self, desconexion=False):
        with self.lock:
            self.fase = None
            self.inicio = None
            self.muestras = 0
            if desconexion:
                self.ultimo_sondeo = None
            self.aviso = 'Secuencia detenida; evento desactivado. Lo recibido por BOL no se revierte.'

    def rearmar(self):
        with self.lock:
            self.cancelar()
            self.caidos = self.antes = frozenset()
            self.aviso = 'Rack local vacío de caídos. No cambia turno ni reinicia la partida de BOL.'

    def responder(self, frame):
        with self.lock:
            if not valido(frame):
                return None
            if len(frame)==5 and frame[1]==0xA5 and frame[2] in (0x81,0x82):
                return paquete(frame[1:3])
            if len(frame)!=11 or frame[1]!=0x81:
                return None
            now = self.reloj()
            self.ultimo_sondeo = now
            self.total_sondeos += 1
            if self.fase is not None:
                if self.inicio is None:
                    self.inicio = now
                elif self.muestras >= 2 and now-self.inicio >= self.duracion:
                    self.fase += 1
                    self.inicio = now
                    self.muestras = 0
                    if self.fase == len(self.FASES):
                        self.fase = None
                        self.aviso = 'Secuencia servida por COM2. Verificar puntuación y turno en la VM.'
                if self.fase is not None:
                    self.muestras += 1
            fase = self.FASES[self.fase] if self.fase is not None else 'reposo'
            pins = self.antes if self.fase in (0,1) else self.caidos
            return paquete(bytes([0x91])+estado(pins, fase))
