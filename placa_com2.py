"""Respondedor COM2 de laboratorio. Estado sintético, NO emulación completa."""
import argparse
import sys
from protocolo import Conexion, Decodificador, Registro, paquete, valido


def respuesta(trama, estado):
    if not valido(trama):
        return None
    if len(trama) == 5 and trama[1] == 0xA5 and trama[2] in (0x81, 0x82):
        return paquete(trama[1:3])
    if len(trama) == 11 and trama[1] == 0x81:
        return paquete(bytes([0x91]) + estado)
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='socket://127.0.0.1:5001')
    p.add_argument('--backend', choices=['auto', 'socket', 'pyserial'], default='auto')
    p.add_argument('--estado', default='80 A0 80 80 80 80 80 80 80 80 80',
                   help='11 bytes de estado, índices 2..12 de la trama de respuesta.')
    p.add_argument('--log', default='placa_com2.log')
    a = p.parse_args()
    try:
        estado = bytes.fromhex(a.estado)
        if len(estado) != 11:
            raise ValueError('Se requieren exactamente 11 bytes de estado.')
        paquete(bytes([0x91]) + estado)
    except ValueError as e:
        p.error(str(e))
    reg, conn = Registro(a.log), None
    try:
        reg.log('COM2 EXPERIMENTAL: responde sondeos, no simula tiros ni mecánica completa.')
        conn = Conexion(a.url, a.backend, 19200)
        reg.log(f'Conectado a {a.url} con {conn.backend}; estado={estado.hex(" ")}')
        decoder = Decodificador()
        anterior = None
        contador = 0
        while True:
            data = conn.read()
            for frame in decoder.feed(data):
                tx = respuesta(frame, estado)
                if tx is not None:
                    conn.write(tx)
                par = (frame, tx)
                contador += 1
                # Guardar cambios y una muestra cada 100 paquetes; evitar logs enormes.
                if par != anterior or contador % 100 == 0:
                    reg.log(f'#{contador} RX {frame.hex(" ").upper()} '
                            f'TX {tx.hex(" ").upper() if tx else "sin respuesta"}')
                    anterior = par
    except (OSError, RuntimeError, ValueError) as e:
        reg.log(f'ERROR: {e}')
        return 1
    except KeyboardInterrupt:
        reg.log('Respondedor detenido.')
    finally:
        if conn:
            conn.close()
        reg.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
