"""Pruebas locales con un cliente que representa el transporte de la VM."""
import queue
import socket
import tempfile
import time
import unittest
from pathlib import Path
from protocolo import comando, paquete, valido
from servidor import Puerto, cargar_pista


def recibir(s, cantidad):
    r = b''
    while len(r) < cantidad:
        b = s.recv(cantidad-len(r))
        if not b:
            raise ConnectionError('Conexión cerrada')
        r += b
    return r


class Red(unittest.TestCase):
    def setUp(self):
        self.q = queue.Queue()
        self.p = Puerto('COM1', self.q)
        self.port = self.p.start('127.0.0.1', 0)
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.p.stop(); self.p.hilo.join(2)
        self.assertFalse(self.p.hilo.is_alive())

    def evento(self, tipo):
        limit = time.monotonic()+2
        while time.monotonic() < limit:
            e = self.q.get(timeout=2)
            if e['tipo'] == tipo:
                return e
        self.fail('No llegó evento ' + tipo)

    def conectar(self):
        c = socket.create_connection(('127.0.0.1', self.port), timeout=2)
        self.clients.append(c)
        self.evento('conectado')
        return c

    def test_paced_tx_y_respuesta_fragmentada(self):
        c = self.conectar()
        p = comando(6, 0x81)
        start = time.monotonic()
        self.p.send(p, 10)
        self.assertEqual(recibir(c, 5), bytes.fromhex('1B 26 81 D9 04'))
        self.assertGreaterEqual(time.monotonic()-start, 0.03)
        c.sendall(bytes.fromhex('1B 26'))
        c.sendall(bytes.fromhex('C3 97 04'))
        e = self.evento('trama')
        self.assertTrue(e['valida'])
        self.assertEqual(e['datos'], bytes.fromhex('1B 26 C3 97 04'))

    def test_desconexion_y_reconexion(self):
        c = self.conectar(); c.close()
        self.evento('desconectado')
        with self.assertRaises(ConnectionError):
            self.p.send(b'123')
        c2 = self.conectar()
        self.p.send(comando(6, 0xC0), 0)
        self.assertEqual(recibir(c2, 5), bytes.fromhex('1B 26 C0 9A 04'))

    def test_checksum_erroneo_no_valida(self):
        c = self.conectar()
        c.sendall(bytes.fromhex('1B 26 C3 98 04'))
        self.assertFalse(self.evento('trama')['valida'])

    def test_com2_responde_sin_intervencion_tk(self):
        self.p.auto_placa = True
        c = self.conectar()
        c.sendall(bytes.fromhex('1B A5 82 D9 04'))
        self.assertEqual(recibir(c, 5), bytes.fromhex('1B A5 82 D9 04'))
        c.sendall(paquete(bytes.fromhex('81 80 80 80 80 80 80 80')))
        r = recibir(c, 15)
        self.assertTrue(valido(r)); self.assertEqual(r[1], 0x91)


class Config(unittest.TestCase):
    def test_archivos_antiguos_no_se_modifican(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'BOLICHE.INI'
            raw = b'[]\r\n[Pista]\r\nNumero desta pista=6\r\n'
            f.write_bytes(raw)
            self.assertEqual(cargar_pista(f), 6)
            self.assertEqual(f.read_bytes(), raw)
            f.write_text('Porta Serial=1\nTaxa de Comunicacao=115\nEndereco=7')
            self.assertEqual(cargar_pista(f), 7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
