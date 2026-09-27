"""Consola Tkinter de diagnóstico para BOL.EXE. Python escucha; VM conecta."""
import datetime
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from protocolo import comando, valido
from servidor import Puerto, cargar_pista


class App:
    def __init__(self, root, logdir=None):
        self.root = root
        root.title('BOL.EXE · Consola de pista — TCP servidor')
        root.geometry('1040x780')
        root.minsize(880, 650)
        self.eventos = queue.Queue()
        self.puertos = {n: Puerto(n, self.eventos) for n in ('COM1', 'COM2')}
        self.connected = set()
        self.pending = None
        self.demo = []
        self.demo_due = None
        self.counts = {n: [0, 0] for n in self.puertos}
        self.token = 0
        self.closed = False
        folder = Path(logdir) if logdir else Path(__file__).resolve().parent / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        self.logpath = folder / ('bolos_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.log')
        self.logfile = self.logpath.open('w', encoding='utf-8', buffering=1)
        self.host = tk.StringVar(value='127.0.0.1')
        self.ports = {'COM1': tk.StringVar(value='5000'), 'COM2': tk.StringVar(value='5001')}
        self.pista = tk.StringVar(value='6')
        self.pausa = tk.StringVar(value='5')
        self.auto = tk.BooleanVar(value=False)
        self.estado_texto = tk.StringVar(value='80 A0 80 80 80 80 80 80 80 80 80')
        self.status = {n: tk.StringVar(value='Detenido') for n in self.puertos}
        self.resultado = tk.StringVar(value='Sin respuesta BOL verificada en esta sesión.')
        self.stats = tk.StringVar(value='COM1 TX 0 / RX 0 bytes   |   COM2 TX 0 / RX 0 bytes')
        self.equipo = tk.StringVar(value='DEMO')
        self.jugadores = tk.StringVar(value='PRUEBA')
        self.raw = tk.StringVar(value='1B 26 81 D9 04')
        self.raw_port = tk.StringVar(value='COM1')
        self._ui()
        self.log('INFO', 'GUI v2: servidor TCP crudo. No prueba por sí misma que BOL.EXE reciba bytes.')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.timer = root.after(40, self.poll)

    def _ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='BOL.EXE · Laboratorio de comunicación', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='1. Iniciar escucha   →   2. Encender VM   →   3. Ejecutar BOL.EXE y consultar',
                  font=('Segoe UI', 10)).pack(anchor='w', pady=(2, 8))
        box = ttk.LabelFrame(outer, text='Conexiones: Python servidor / VirtualBox cliente', padding=8)
        box.pack(fill='x')
        ttk.Label(box, text='Escuchar en').grid(row=0, column=0, sticky='w')
        ttk.Entry(box, textvariable=self.host, width=17).grid(row=0, column=1, padx=5)
        ttk.Label(box, text='Pista').grid(row=0, column=2)
        ttk.Entry(box, textvariable=self.pista, width=5).grid(row=0, column=3, padx=5)
        ttk.Button(box, text='Leer INI / CFG…', command=self.load_config).grid(row=0, column=4, padx=5)
        ttk.Label(box, text='Pausa COM1 (ms/byte)').grid(row=0, column=5)
        ttk.Entry(box, textvariable=self.pausa, width=5).grid(row=0, column=6, padx=5)
        for i, n in enumerate(self.puertos, 1):
            ttk.Label(box, text=n + (' · central' if i == 1 else ' · placa')).grid(row=i, column=0, sticky='w', pady=5)
            ttk.Entry(box, textvariable=self.ports[n], width=17).grid(row=i, column=1)
            ttk.Button(box, text='Escuchar', command=lambda n=n: self.start(n)).grid(row=i, column=2, columnspan=2)
            ttk.Button(box, text='Detener', command=lambda n=n: self.stop(n)).grid(row=i, column=4)
            ttk.Label(box, textvariable=self.status[n]).grid(row=i, column=5, columnspan=2, sticky='w')
        notebook = ttk.Notebook(outer)
        self.notebook = notebook
        notebook.pack(fill='x', pady=10)
        ctl = ttk.Frame(notebook, padding=10)
        notebook.add(ctl, text='Central / COM1')
        self.buttons = []
        for col, (label, code, expected) in enumerate([
            ('Consultar estado', 0x81, {0xC3, 0xFC, 0xD6, 0xEC, 0xC6}),
            ('Entrenamiento', 0xC0, {0xC2}), ('Solicitar reposo', 0x86, {0xC7})]):
            b = ttk.Button(ctl, text=label, command=lambda c=code, e=expected, l=label: self.command(c, b'', e, l))
            b.grid(row=0, column=col, padx=(0, 8), sticky='w')
            self.buttons.append(b)
        ttk.Label(ctl, text='Equipo (máx. 9):').grid(row=1, column=0, sticky='w', pady=(10, 2))
        ttk.Entry(ctl, textvariable=self.equipo, width=15).grid(row=2, column=0, sticky='w')
        ttk.Label(ctl, text='Jugadores separados por coma (máx. 10, nombres de 9):').grid(row=1, column=1, columnspan=3, sticky='w')
        ttk.Entry(ctl, textvariable=self.jugadores, width=48).grid(row=2, column=1, columnspan=3, sticky='ew')
        self.demo_button = ttk.Button(ctl, text='Iniciar DEMO experimental', command=self.start_demo)
        self.demo_button.grid(row=3, column=0, columnspan=2, sticky='w', pady=8)
        self.buttons.append(self.demo_button)
        ttk.Button(ctl, text='Cancelar secuencia', command=self.cancel).grid(row=3, column=2)
        ttk.Label(ctl, text='DEMO cambia la sesión. Un ACK confirma recepción, no que el marcador esté listo.').grid(row=4, column=0, columnspan=4, sticky='w')
        board = ttk.Frame(notebook, padding=10)
        notebook.add(board, text='Placa / COM2 — experimental')
        ttk.Checkbutton(board, text='Responder automáticamente a las consultas de BOL.EXE', variable=self.auto,
                        command=self.apply_board).pack(anchor='w')
        ttk.Label(board, text='11 bytes de estado sintético (sin cabecera ni checksum):').pack(anchor='w', pady=(8, 2))
        row = ttk.Frame(board); row.pack(fill='x')
        ttk.Entry(row, textvariable=self.estado_texto, width=52).pack(side='left')
        ttk.Button(row, text='Aplicar estado', command=self.apply_board).pack(side='left', padx=8)
        ttk.Label(board, text='No simula una partida completa ni tiros. Puerto TCP recomendado: 5001 → COM2 de la VM.').pack(anchor='w', pady=8)
        raw = ttk.Frame(notebook, padding=10); notebook.add(raw, text='Trama manual')
        ttk.Label(raw, text='Trama BOL completa: 1B … checksum … 04. No acepta bloques sin enmarcar.').pack(anchor='w')
        row = ttk.Frame(raw); row.pack(fill='x', pady=8)
        ttk.Combobox(row, textvariable=self.raw_port, values=['COM1', 'COM2'], state='readonly', width=7).pack(side='left')
        ttk.Entry(row, textvariable=self.raw, width=68).pack(side='left', padx=8, fill='x', expand=True)
        ttk.Button(row, text='Enviar', command=self.raw_send).pack(side='left')
        ttk.Label(raw, text='El protocolo de transferencia GLINK es distinto. Esta consola decodifica BOL, no GLINK.').pack(anchor='w')
        ttk.Label(outer, textvariable=self.resultado, wraplength=970, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        ttk.Label(outer, textvariable=self.stats).pack(anchor='w')
        self.console = ScrolledText(outer, height=13, font=('Consolas', 9), state='disabled', wrap='none')
        self.console.pack(fill='both', expand=True, pady=5)
        footer = ttk.Frame(outer); footer.pack(fill='x')
        ttk.Button(footer, text='Guardar copia del registro…', command=self.save_log).pack(side='left')
        ttk.Label(footer, text='Registro automático en la carpeta logs/').pack(side='left', padx=10)

    def log(self, tipo, texto):
        s = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3] + f' {tipo} {texto}\n'
        self.logfile.write(s)
        self.console.configure(state='normal')
        self.console.insert('end', s)
        if int(self.console.index('end-1c').split('.')[0]) > 2200:
            self.console.delete('1.0', '300.0')
        self.console.see('end'); self.console.configure(state='disabled')

    def error(self, e):
        self.log('ERROR', str(e)); self.resultado.set(str(e))

    def load_config(self):
        path = filedialog.askopenfilename(title='BOLICHE.INI o GLINK.CFG', filetypes=[('Configuración', '*.ini *.INI *.cfg *.CFG'), ('Todos', '*')])
        if path:
            try:
                n = cargar_pista(path)
                self.pista.set(str(n))
                self.log('CONFIG', f'Pista {n}, dirección {n+32:02X}, leída de {path}. Archivo sin modificar.')
            except (OSError, ValueError) as e:
                self.error(e)

    def start(self, n):
        try:
            port = int(self.ports[n].get())
            if not 1 <= port <= 65535:
                raise ValueError('Puerto TCP fuera de rango.')
            self.puertos[n].start(self.host.get().strip(), port)
        except (OSError, ValueError, RuntimeError) as e:
            self.error(f'{n}: {e}. Si está ocupado, cerrar serverbolos.py u otra instancia.')

    def stop(self, n):
        if n == 'COM1':
            self.cancel()
        self.puertos[n].stop()

    def apply_board(self):
        try:
            b = bytes.fromhex(self.estado_texto.get())
            if len(b) != 11 or any(x in (4, 27) for x in b):
                raise ValueError('COM2 requiere 11 bytes sin 1B ni 04.')
            self.puertos['COM2'].estado = b
            self.puertos['COM2'].auto_placa = self.auto.get()
            self.log('COM2', f'Auto={self.auto.get()}, estado={b.hex(" ").upper()} (experimental)')
        except ValueError as e:
            self.auto.set(False)
            self.puertos['COM2'].auto_placa = False
            self.error(e)

    def command(self, code, payload, expected, label):
        try:
            if self.pending:
                raise ValueError('Hay una respuesta pendiente. Esperar o cancelar.')
            n = int(self.pista.get())
            delay = float(self.pausa.get())
            if not 0 <= delay <= 100:
                raise ValueError('Pausa permitida: 0 a 100 ms por byte.')
            data = comando(n, code, payload)
            self.token += 1
            self.puertos['COM1'].send(data, delay, self.token)
            self.pending = dict(expected=expected, address=n+32, label=label, token=self.token,
                                deadline=time.monotonic()+4+len(data)*delay/1000)
            self.resultado.set(label + ': esperando respuesta de BOL.EXE…')
            self.log('SOLICITUD', label + ' | ' + data.hex(' ').upper())
        except (ValueError, OSError) as e:
            self.demo = []; self.demo_due = None
            self.error(e)

    def start_demo(self):
        try:
            def nombre(s):
                b = s.strip().encode('ascii')
                if not 1 <= len(b) <= 9 or any(x < 32 or x > 126 for x in b):
                    raise ValueError('Nombres: 1 a 9 caracteres ASCII imprimibles.')
                return b.ljust(9, b' ')
            team = nombre(self.equipo.get())
            players = [nombre(s) for s in self.jugadores.get().split(',')]
            if not 1 <= len(players) <= 10:
                raise ValueError('Se admiten de 1 a 10 jugadores.')
            if self.pending or self.demo:
                raise ValueError('Ya hay una operación en curso.')
            self.demo = [(0x81, b'', {0xC3,0xFC,0xD6,0xEC,0xC6}, 'DEMO: consultar'),
                         (0x82, b'00101003', {0xC4}, 'DEMO: iniciar sesión'),
                         (0x8C, team, {0xDC}, 'DEMO: equipo')]
            self.demo += [(0x8D+i, b+b'000', {0xDD+i}, f'DEMO: jugador {i+1}') for i,b in enumerate(players)]
            self.demo.append((0x97, b'', {0xE7}, 'DEMO: fin de nombres'))
            self.demo_due = time.monotonic()
        except ValueError as e:
            self.error(e)

    def cancel(self):
        self.pending = None; self.demo = []; self.demo_due = None
        self.resultado.set('Espera/secuencia cancelada. Lo ya enviado no se deshace.')
        self.log('INFO', 'Cancelada la secuencia pendiente; no revierte bytes ya enviados.')

    def raw_send(self):
        try:
            n = self.raw_port.get()
            if n == 'COM1' and (self.pending or self.demo):
                raise ValueError('Cancelar o terminar la secuencia antes de enviar manualmente.')
            data = bytes.fromhex(self.raw.get())
            if not valido(data):
                raise ValueError('Trama inválida: debe empezar en 1B, terminar en 04 y pasar checksum.')
            if len(data) > 254:
                raise ValueError('Trama demasiado larga.')
            delay = float(self.pausa.get()) if n == 'COM1' else 0
            if not 0 <= delay <= 100:
                raise ValueError('Pausa fuera de rango.')
            self.puertos[n].send(data, delay)
            self.resultado.set('Trama manual encolada; observar RX. No se presume un ACK.')
        except (ValueError, OSError) as e:
            self.error(e)

    def handle(self, e):
        n, tipo = e['puerto'], e['tipo']
        if tipo == 'escucha':
            self.status[n].set('Escuchando · sin VM')
            self.log(n, f'Escuchando en {e["direccion"]}')
        elif tipo == 'conectado':
            self.connected.add(n); self.status[n].set('TCP conectado · BOL no verificado')
            self.log(n, f'TCP conectado desde {e["direccion"]}; esto no identifica el programa invitado.')
        elif tipo in ('desconectado', 'detenido'):
            self.connected.discard(n)
            self.status[n].set('Escuchando · sin VM' if tipo == 'desconectado' else 'Detenido')
            if n == 'COM1':
                self.pending = None; self.demo = []; self.demo_due = None
                self.resultado.set('COM1 desconectado. Volver a consultar después de reconectar.')
            self.log(n, tipo)
        elif tipo in ('rx', 'tx'):
            b = e['datos']; self.counts[n][0 if tipo == 'tx' else 1] += len(b)
            self.log(n + ' ' + tipo.upper(), b.hex(' ').upper() + ' |' + ''.join(chr(x) if 32 <= x <= 126 else '.' for x in b) + '|')
        elif tipo == 'trama':
            b = e['datos']
            self.log(n + ' TRAMA', b.hex(' ').upper() + f' | checksum={e["valida"]}')
            p = self.pending
            if (n == 'COM1' and p and e['valida'] and len(b) >= 5
                    and b[1] == p['address'] and b[2] in p['expected']):
                self.status[n].set('Respuesta BOL compatible recibida')
                self.resultado.set(f'{p["label"]}: respuesta {b[2]:02X} recibida. Verificar la pantalla de la VM.')
                self.pending = None
                if self.demo:
                    self.demo_due = time.monotonic() + 1.5
        elif tipo == 'error':
            self.error(n + ': ' + e['texto'])

    def poll(self):
        if self.closed:
            return
        for _ in range(250):
            try:
                self.handle(self.eventos.get_nowait())
            except queue.Empty:
                break
        if self.pending and time.monotonic() > self.pending['deadline']:
            self.log('TIMEOUT', self.pending['label'] + ': sin respuesta compatible. No se reintenta.')
            self.pending = None; self.demo = []; self.demo_due = None
            self.resultado.set('TCP puede estar conectado, pero BOL.EXE no respondió. Revisar puerto invitado, pantalla y log.')
        if self.demo and self.demo_due is not None and time.monotonic() >= self.demo_due and not self.pending:
            step = self.demo.pop(0); self.demo_due = None
            self.command(*step)
        enabled = 'normal' if 'COM1' in self.connected and not self.pending and not self.demo else 'disabled'
        for b in self.buttons:
            b.configure(state=enabled)
        self.stats.set('   |   '.join(f'{n} TX {v[0]} / RX {v[1]} bytes' for n,v in self.counts.items()))
        self.timer = self.root.after(40, self.poll)

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension='.log', initialfile=self.logpath.name)
        if path:
            try:
                self.logfile.flush()
                if Path(path).resolve() != self.logpath.resolve():
                    Path(path).write_bytes(self.logpath.read_bytes())
            except OSError as e:
                self.error(e)

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        for p in self.puertos.values():
            p.stop()
        for p in self.puertos.values():
            if p.hilo:
                p.hilo.join(timeout=0.5)
        self.logfile.close()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    try:
        app = App(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror('BOL GUI', str(e))
        raise
