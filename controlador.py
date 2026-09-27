"""Parte 2: control remoto experimental de sensores para BOL.EXE."""
import time
import tkinter as tk
from tkinter import ttk
from bolos_gui import App
from tiradas import ControlTiradas

class Controlador(App):
    def __init__(self, root, logdir=None):
        self.control = ControlTiradas()
        self.last_phase = object()
        super().__init__(root, logdir)
        root.title('BOL · Control remoto de tiradas — experimental')
        self.puertos['COM2'].board_handler = self.control.responder
        self.puertos['COM2'].auto_placa = True
        self.log('CONTROL', 'Respondedor COM2 activo. No hay confirmación automática del marcador.')

    def _ui(self):
        super()._ui()
        for tab in self.notebook.tabs():
            if self.notebook.tab(tab,'text').startswith('Placa /'):
                self.notebook.hide(tab)
        panel = ttk.Frame(self.notebook, padding=8)
        self.notebook.insert(0,panel,text='Tiradas / COM2')
        self.notebook.select(panel)
        self.pinvars = {i:tk.BooleanVar(value=False) for i in range(1,11)}
        self.dwell = tk.StringVar(value='1.0')
        self.remote_status = tk.StringVar(value='Esperando sondeos COM2 de BOL.EXE.')
        self.rack_status = tk.StringVar(value='')
        left = ttk.Frame(panel); left.grid(row=0,column=0,rowspan=4,padx=(0,20))
        ttk.Label(left,text='Marcar pinos nuevos que caen:').grid(row=0,column=0,columnspan=7)
        for row, pins in enumerate(((7,8,9,10),(4,5,6),(2,3),(1,)),1):
            for j,pin in enumerate(pins):
                col = 4-len(pins)+2*j
                ttk.Checkbutton(left,text=str(pin),variable=self.pinvars[pin]).grid(row=row,column=col,sticky='w')
        presets = ttk.Frame(panel); presets.grid(row=0,column=1,sticky='w')
        for label,count in [('0 pinos',0),('5 pinos',5),('Todos restantes',10)]:
            ttk.Button(presets,text=label,command=lambda n=count:self.preset(n)).pack(side='left',padx=3)
        actions = ttk.Frame(panel); actions.grid(row=1,column=1,sticky='w',pady=6)
        ttk.Button(actions,text='Enviar tirada',command=self.throw).pack(side='left',padx=3)
        ttk.Button(actions,text='Cancelar ciclo',command=self.abort).pack(side='left',padx=3)
        ttk.Button(actions,text='Nuevo rack',command=self.reset_rack).pack(side='left',padx=3)
        timing = ttk.Frame(panel); timing.grid(row=2,column=1,sticky='w')
        ttk.Label(timing,text='Segundos mínimos por fase:').pack(side='left')
        ttk.Entry(timing,textvariable=self.dwell,width=5).pack(side='left',padx=5)
        ttk.Label(timing,text='(mínimo 2 sondeos por fase)').pack(side='left')
        ttk.Label(panel,textvariable=self.rack_status).grid(row=3,column=1,sticky='w')
        ttk.Label(panel,textvariable=self.remote_status,wraplength=920).grid(row=4,column=0,columnspan=2,sticky='w',pady=4)
        ttk.Label(panel,text='Requiere partida activa en BOL. El número mostrado aquí es local; verificar el marcador en la VM.').grid(row=5,column=0,columnspan=2,sticky='w')

    def preset(self, count):
        fallen = set(self.control.snapshot()['caidos'])
        available = [p for p in range(1,11) if p not in fallen]
        if count==5 and len(available)<5:
            self.error('Quedan menos de 5 pinos. Elegir los restantes o verificar si corresponde Nuevo rack.')
            return
        chosen = set(available[:count])
        for p,v in self.pinvars.items():
            v.set(p in chosen)

    def throw(self):
        try:
            if 'COM2' not in self.connected:
                raise ValueError('Primero conectar COM2 de la VM al servidor TCP 5001.')
            pins = [p for p,v in self.pinvars.items() if v.get()]
            self.control.lanzar(pins,float(self.dwell.get()))
            self.log('TIRADA',f'Nuevos={pins}; mínimo {self.dwell.get()} s/fase. Solicitud, no puntuación confirmada.')
            self.preset(0)
        except ValueError as e:
            self.error(e)

    def abort(self):
        self.control.cancelar()
        self.log('TIRADA','Cancelada. El siguiente sondeo recibirá evento=0; no se revierte lo enviado.')

    def reset_rack(self):
        self.control.rearmar()
        self.preset(0)
        self.log('TIRADA','Nuevo rack local. Verificar que BOL esté esperando otro rack.')

    def raw_send(self):
        if self.raw_port.get()=='COM2':
            self.error('COM2 está reservado al controlador de tiradas. Usar selección de pinos y Cancelar ciclo.')
        else:
            super().raw_send()

    def handle(self,e):
        if e['puerto']=='COM2' and e['tipo'] in ('conectado','desconectado','detenido'):
            self.control.cancelar(desconexion=True)
        super().handle(e)

    def stop(self,n):
        if n=='COM2':
            self.control.cancelar(desconexion=True)
        super().stop(n)

    def poll(self):
        super().poll()
        if self.closed:
            return
        s = self.control.snapshot()
        phase = 'reposo' if s['fase'] is None else self.control.FASES[s['fase']]
        age = 'sin sondeos' if s['ultimo'] is None else f'último hace {time.monotonic()-s["ultimo"]:.1f} s'
        self.rack_status.set(f'Caídos acumulados locales: {s["caidos"] or "ninguno"}')
        self.remote_status.set(f'Fase: {phase} · sondeos: {s["sondeos"]} · {age}. {s["aviso"]}')
        marker=(s['fase'],tuple(s['caidos']),s['aviso'])
        if marker!=self.last_phase:
            self.log('FASE',f'{phase}; caídos={s["caidos"]}; {s["aviso"]}')
            self.last_phase=marker

if __name__=='__main__':
    root=tk.Tk()
    app=Controlador(root)
    root.mainloop()
