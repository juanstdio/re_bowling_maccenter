"""Protocolo recuperado de BOL.EXE 3.0.0.1.3. No ejecuta el EXE."""
import socket
import time
from urllib.parse import urlparse

STX, EOT = 0x1B, 0x04


def paquete(cuerpo):
    cuerpo = bytes(cuerpo)
    if not cuerpo or any(x in (STX, EOT) for x in cuerpo):
        raise ValueError('El cuerpo no puede contener 1B ni 04: no hay escape identificado.')
    if len(cuerpo) > 250:
        raise ValueError('Paquete demasiado largo.')
    return bytes([STX]) + cuerpo + bytes([((-sum(cuerpo)) & 0x7F) | 0x80, EOT])


def comando(pista, codigo, datos=b''):
    if not 1 <= pista <= 32:
        raise ValueError('Este laboratorio admite pistas 1 a 32.')
    if not 0x80 <= codigo <= 0xFF:
        raise ValueError('El comando debe ser un byte entre 80 y FF.')
    return paquete(bytes([0x20 + pista, codigo]) + datos)


def valido(p):
    return (len(p) >= 4 and p[0] == STX and p[-1] == EOT
            and not any(x in (STX, EOT) for x in p[1:-1])
            and sum(p[1:-1]) & 0x7F == 0)


class Decodificador:
    """Admite fragmentación TCP, varios paquetes juntos y resincronización."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, datos):
        resultado = []
        for x in datos:
            if x == STX:
                self.buffer = bytearray([x])
            elif self.buffer:
                self.buffer.append(x)
                if x == EOT:
                    resultado.append(bytes(self.buffer))
                    self.buffer.clear()
                elif len(self.buffer) > 256:
                    self.buffer.clear()
        return resultado


class Conexion:
    """TCP crudo, o pySerial opcional. El socket no negocia baudrate/RTS."""
    def __init__(self, url, backend='auto', baudrate=9600):
        u = urlparse(url)
        if u.scheme != 'socket' or not u.hostname or not u.port:
            raise ValueError('Usar socket://127.0.0.1:5000 (TCP crudo de VirtualBox).')
        self.serial = None
        self.sock = None
        if backend in ('auto', 'pyserial'):
            try:
                import serial
            except ImportError:
                if backend == 'pyserial':
                    raise RuntimeError('Falta pyserial: python -m pip install pyserial')
            else:
                self.serial = serial.serial_for_url(
                    url, baudrate=baudrate, bytesize=8, parity='N', stopbits=2,
                    timeout=0.10, write_timeout=2, xonxoff=False, rtscts=False,
                    dsrdtr=False)
        if self.serial is None:
            self.sock = socket.create_connection((u.hostname, u.port), timeout=3)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(0.10)
        self.backend = 'pyserial' if self.serial else 'socket nativo'

    def write(self, datos):
        if self.serial:
            n = self.serial.write(datos)
            if n != len(datos):
                raise OSError('Escritura incompleta.')
        else:
            self.sock.sendall(datos)

    def read(self):
        if self.serial:
            return self.serial.read(max(1, min(4096, self.serial.in_waiting)))
        try:
            datos = self.sock.recv(4096)
        except socket.timeout:
            return b''
        if not datos:
            raise ConnectionError('VirtualBox cerró la conexión TCP.')
        return datos

    def close(self):
        if self.serial:
            self.serial.close()
        if self.sock:
            self.sock.close()


class Registro:
    def __init__(self, nombre):
        self.f = open(nombre, 'a', encoding='utf-8', buffering=1)

    def log(self, texto):
        linea = time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + texto
        print(linea, flush=True)
        self.f.write(linea + '\n')

    def close(self):
        self.f.close()
