import queue
import socket
import unittest
from protocolo import paquete, valido
from tiradas import ControlTiradas, estado
from servidor import Puerto
from pruebas import recibir

POLL = paquete(bytes.fromhex('81 80 80 80 80 80 80 80'))

class Tiradas(unittest.TestCase):
    def setUp(self):
        self.now=0.0
        self.c=ControlTiradas(lambda:self.now)

    def test_1024_combinaciones_sensores(self):
        # Orden leído en 1D8AA..1F23E; máscara independiente de SENSORES.
        mapping=((2,16),(2,8),(3,2),(2,2),(3,1),(3,8),(2,1),(2,4),(3,4),(3,16))
        for m in range(1024):
            selected={i+1 for i in range(10) if m & (1<<i)}
            p=paquete(bytes([0x91])+estado(selected,'lectura'))
            decoded={i+1 for i,(byte,bit) in enumerate(mapping) if p[byte]&bit}
            self.assertEqual(decoded,selected)
            self.assertEqual(len(p),15)
            self.assertTrue(valido(p))

    def test_sin_consultas_no_dispara(self):
        with self.assertRaises(ValueError): self.c.lanzar({1})
        self.c.responder(POLL)
        self.now=11
        with self.assertRaises(ValueError): self.c.lanzar({1})

    def test_secuencia_cinco_y_sin_avance_por_reloj_solo(self):
        self.c.responder(POLL)
        self.c.lanzar({1,2,3,4,5})
        frames=[]
        for i in range(4):
            frames.append(self.c.responder(POLL))
            self.now+=20  # una sola consulta NO basta aunque transcurra tiempo
            self.assertEqual(self.c.snapshot()['fase'],i)
            self.c.responder(POLL)
        # Tramas constantes: reposo vacío, inicio vacío, lectura cinco, retorno cinco.
        self.assertEqual(frames[0][2:6],bytes.fromhex('80 A0 80 80'))
        self.assertEqual(frames[1][2:6],bytes.fromhex('80 80 80 80'))
        self.assertEqual(frames[2][2:6],bytes.fromhex('9A 83 80 81'))
        self.assertEqual(frames[3][2:6],bytes.fromhex('9A A3 80 80'))
        self.c.responder(POLL)
        self.assertIsNone(self.c.snapshot()['fase'])

    def test_segunda_bola_acumula_y_rearmado(self):
        self.c.responder(POLL); self.c.lanzar({1,2,3,4,5})
        self.c.cancelar()
        with self.assertRaises(ValueError): self.c.lanzar({1})
        self.c.lanzar({6,7})
        self.assertEqual(self.c.snapshot()['caidos'],list(range(1,8)))
        self.c.rearmar()
        self.assertEqual(self.c.snapshot()['caidos'],[])

    def test_cancelacion_desconexion_y_checksum(self):
        self.c.responder(POLL); self.c.lanzar({1})
        count=self.c.snapshot()['sondeos']
        bad=POLL[:-2]+bytes([POLL[-2]^1,4])
        self.assertIsNone(self.c.responder(bad))
        self.assertEqual(self.c.snapshot()['sondeos'],count)
        self.c.cancelar(desconexion=True)
        self.assertIsNone(self.c.snapshot()['ultimo'])
        with self.assertRaises(ValueError): self.c.lanzar({2})
        reply=self.c.responder(POLL)
        self.assertEqual(reply[5]&1,0)
        self.assertEqual(reply[3]&32,32)

    def test_cero_y_diez(self):
        for pins in (set(),set(range(1,11))):
            self.c.rearmar(); self.c.responder(POLL); self.c.lanzar(pins)
            self.assertEqual(set(self.c.snapshot()['caidos']),pins)
        self.assertEqual(estado(range(1,11),'lectura')[:2],bytes.fromhex('9F 9F'))

    def test_ciclo_completo_sobre_tcp(self):
        q=queue.Queue(); p=Puerto('COM2',q,auto_placa=True)
        p.board_handler=self.c.responder
        port=p.start('127.0.0.1',0)
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=2) as s:
                s.sendall(bytes.fromhex('1B A5 82 D9 04'))
                self.assertEqual(recibir(s,5),bytes.fromhex('1B A5 82 D9 04'))
                s.sendall(POLL); self.assertTrue(valido(recibir(s,15)))
                self.c.lanzar({1,2,3,4,5})
                phases=[]
                for i in range(9):
                    s.sendall(POLL)
                    r=recibir(s,15)
                    self.assertTrue(valido(r))
                    phases.append((bool(r[3]&32),bool(r[5]&1)))
                    self.now+=1
                self.assertEqual(phases,[(True,False)]*2+[(False,False)]*2+[(False,True)]*2+[(True,False)]*3)
                self.assertIsNone(self.c.snapshot()['fase'])
        finally:
            p.stop(); p.hilo.join(2)
        self.assertFalse(p.hilo.is_alive())

if __name__=='__main__': unittest.main(verbosity=2)
