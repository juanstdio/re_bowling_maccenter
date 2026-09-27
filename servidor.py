"""Servidor TCP crudo para una UART de VirtualBox; sin dependencias externas."""
import queue
import socket
import threading
import time
from protocolo import Decodificador, valido
from placa_com2 import respuesta


class Puerto:
    def __init__(self, nombre, eventos, auto_placa=False):
        self.nombre, self.eventos = nombre, eventos
        self.auto_placa = auto_placa
        self.estado = bytes.fromhex('80 A0 80 80 80 80 80 80 80 80 80')
        self.listener = self.cliente = self.hilo = None
        self.parar = threading.Event()
        self.lock = threading.Lock()
        self.cola = queue.Queue()
        self.sesion = 0

    def evento(self, tipo, **datos):
        self.eventos.put(dict(puerto=self.nombre, tipo=tipo, **datos))

    def start(self, host, port):
        if self.hilo and self.hilo.is_alive():
            raise RuntimeError('Este puerto ya está iniciado.')
        s = socket.socket()
        try:
            # No permitir dos procesos escuchando el mismo puerto en Windows.
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind((host, port))
            s.listen(1)
            s.settimeout(0.10)
        except Exception:
            s.close()
            raise
        self.listener = s
        self.parar.clear()
        self.cola = queue.Queue()
        self.evento('escucha', direccion=s.getsockname())
        self.hilo = threading.Thread(target=self._run, daemon=True)
        self.hilo.start()
        return s.getsockname()[1]

    def send(self, datos, pausa_ms=5, token=None):
        with self.lock:
            if self.cliente is None:
                raise ConnectionError('No hay VM conectada a este puerto.')
            self.cola.put((self.sesion, bytes(datos), pausa_ms / 1000, token))

    def _run(self):
        try:
            while not self.parar.is_set():
                try:
                    c, addr = self.listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self.lock:
                    self.sesion += 1
                    session = self.sesion
                    self.cliente = c
                c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                c.settimeout(0.002)
                self.evento('conectado', direccion=addr)
                decoder = Decodificador()
                envio = None
                try:
                    while not self.parar.is_set():
                        if envio is None:
                            try:
                                ses, data, delay, token = self.cola.get_nowait()
                                if ses == session:
                                    envio = [data, delay, token, 0, 0.0]
                            except queue.Empty:
                                pass
                        if envio and time.monotonic() >= envio[4]:
                            data, delay, token, i, _ = envio
                            fragmento = data[i:i+1] if delay else data[i:]
                            c.sendall(fragmento)
                            envio[3] += len(fragmento)
                            envio[4] = time.monotonic() + delay
                            if envio[3] == len(data):
                                self.evento('tx', datos=data, token=token)
                                envio = None
                        try:
                            data = c.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        self.evento('rx', datos=data)
                        for frame in decoder.feed(data):
                            self.evento('trama', datos=frame, valida=valido(frame))
                            if self.auto_placa:
                                handler = getattr(self, 'board_handler', None)
                                answer = handler(frame) if handler else respuesta(frame, self.estado)
                                if answer:
                                    self.send(answer, pausa_ms=0)
                except OSError as e:
                    if not self.parar.is_set():
                        self.evento('error', texto=str(e))
                finally:
                    with self.lock:
                        self.cliente = None
                    c.close()
                    self.evento('desconectado')
        finally:
            self.listener.close()
            self.evento('detenido')

    def stop(self):
        self.parar.set()
        if self.listener:
            self.listener.close()
        with self.lock:
            if self.cliente:
                try:
                    self.cliente.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


def cargar_pista(path):
    """Acepta el INI antiguo con sección [] y GLINK.CFG sin secciones."""
    from pathlib import Path
    data = Path(path).read_bytes()
    try:
        s = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        s = data.decode('latin1')
    campos = {}
    for linea in s.splitlines():
        if '=' in linea:
            k, v = linea.split('=', 1)
            campos[k.strip().lower()] = v.strip()
    clave = 'numero desta pista' if 'numero desta pista' in campos else 'endereco'
    if clave not in campos:
        raise ValueError('No encontré Numero desta pista ni Endereco.')
    n = int(campos[clave])
    if not 1 <= n <= 32:
        raise ValueError('El laboratorio admite pistas 1 a 32.')
    return n
