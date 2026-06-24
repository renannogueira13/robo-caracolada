# -*- coding: utf-8 -*-
"""
Robo Caracolada - app com interface grafica.
Abre os pacotes do album "Copa SPC Brasil 2026" automaticamente.
Credenciais ficam no arquivo separado: credenciais.json
"""
import os
import sys
import json
import time
import queue
import threading
import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests

APP_TITULO = "Robo Caracolada"
ALBUM_NOME = "Copa SPC Brasil 2026"

# --- config publica (igual para todos; nao e segredo) ---
SUPA = "https://wbyuabdjxtgbzylgbrom.supabase.co"
ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndieXVhYmRqeHRnYnp5bGdicm9tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkwMjEzMTIsImV4cCI6MjA4NDU5NzMxMn0._b3As42NjpPjB1Twq6lfIiZHtvBMUXUKKVRCDGLdOXY"
ALBUM = "b93ee3a6-6a36-4dc0-aaa6-53b28fd9f412"
COOLDOWN = 900          # 15 min
INTERVALO_MIN = 16
MAX_POR_CICLO = 25

# --- cores ---
C_BG = "#0e2148"
C_CARD = "#16306b"
C_YEL = "#ffd23f"
C_TXT = "#ffffff"
C_MUTED = "#9db4e0"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_GRAY = "#64748b"
C_LOGBG = "#0a1733"


def base_dir():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        if ".app/Contents/MacOS" in exe.replace("\\", "/"):
            # macOS: dentro do bundle .app -> usar a pasta que CONTEM o .app
            p = os.path.dirname(exe)
            for _ in range(3):  # MacOS -> Contents -> X.app -> pasta de fora
                p = os.path.dirname(p)
            return p
        return os.path.dirname(exe)   # Windows/Linux: pasta do executavel
    return os.path.dirname(os.path.abspath(__file__))

BASE = base_dir()
CRED_PATH = os.path.join(BASE, "credenciais.json")
LOG_PATH = os.path.join(BASE, "robo.log")


def gravar_log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ---------------- rede ----------------
def login(email, senha):
    r = requests.post(
        f"{SUPA}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON, "Content-Type": "application/json"},
        json={"email": email, "password": senha},
        timeout=30,
    )
    if r.status_code != 200:
        try:
            j = r.json()
            m = j.get("error_description") or j.get("msg") or j.get("error") or r.text[:150]
        except Exception:
            m = r.text[:150]
        raise RuntimeError(m)
    return r.json()["access_token"]


def _h(tok):
    return {"apikey": ANON, "Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def pack_state(tok):
    r = requests.post(f"{SUPA}/rest/v1/rpc/get_my_album_pack_state",
                      headers=_h(tok), json={"_album_id": ALBUM}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})


def abrir_um(tok):
    r = requests.post(f"{SUPA}/functions/v1/open-pack",
                      headers=_h(tok), json={"albumId": ALBUM}, timeout=40)
    try:
        data = r.json()
    except Exception:
        data = {"error": r.text[:150] or f"HTTP {r.status_code}"}
    return r.status_code, data


def resumo(data):
    fig = data.get("stickers") or []
    itens = []
    for s in fig:
        if isinstance(s, dict):
            itens.append(f"#{s.get('number')} {s.get('name', '?')}")
    return (f"{len(fig)} figurinha(s): " + "; ".join(itens)) if itens else "pacote aberto"


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.sessao_abertos = 0
        self.next_ready_at = None

        root.title(APP_TITULO)
        root.configure(bg=C_BG)
        root.geometry("520x600")
        root.minsize(490, 560)

        self._build_ui()
        self._carregar_credenciais()
        self.root.after(150, self._processar_queue)
        self.root.after(1000, self._tick)
        root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=C_BG)
        header.pack(fill="x", padx=20, pady=(18, 4))
        tk.Label(header, text="Robo Caracolada", bg=C_BG, fg=C_YEL,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text=ALBUM_NOME + "   |   abre 1 pacote a cada ~15 min",
                 bg=C_BG, fg=C_MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        # credenciais
        cred = tk.Frame(self.root, bg=C_CARD)
        cred.pack(fill="x", padx=20, pady=10)
        tk.Label(cred, text="E-MAIL DA CARACOLADA", bg=C_CARD, fg=C_MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 0))
        self.e_email = tk.Entry(cred, font=("Segoe UI", 11), relief="flat",
                                bg="#dbe7ff", fg="#0a1733")
        self.e_email.grid(row=1, column=0, padx=12, pady=(2, 8), sticky="we")
        tk.Label(cred, text="SENHA", bg=C_CARD, fg=C_MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="w", padx=12)
        self.e_senha = tk.Entry(cred, font=("Segoe UI", 11), show="*", relief="flat",
                                bg="#dbe7ff", fg="#0a1733")
        self.e_senha.grid(row=3, column=0, padx=12, pady=(2, 12), sticky="we")
        self.btn_salvar = tk.Button(cred, text="Salvar", command=self._salvar_credenciais,
                                    bg=C_GRAY, fg="white", relief="flat", width=8,
                                    font=("Segoe UI", 9, "bold"), cursor="hand2", activebackground="#475569")
        self.btn_salvar.grid(row=1, column=1, rowspan=3, padx=(6, 12))
        cred.columnconfigure(0, weight=1)

        # status
        stt = tk.Frame(self.root, bg=C_CARD)
        stt.pack(fill="x", padx=20, pady=(0, 10))
        self.lbl_status = tk.Label(stt, text="●  Parado", bg=C_CARD, fg=C_GRAY,
                                   font=("Segoe UI", 13, "bold"))
        self.lbl_status.pack(anchor="w", padx=12, pady=(12, 6))
        linha = tk.Frame(stt, bg=C_CARD)
        linha.pack(fill="x", padx=12, pady=(0, 12))
        self.lbl_sessao = tk.Label(linha, text="Abertos agora: 0", bg=C_CARD, fg=C_TXT, font=("Segoe UI", 9))
        self.lbl_sessao.pack(side="left")
        self.lbl_total = tk.Label(linha, text="   |   Total no album: --", bg=C_CARD, fg=C_TXT, font=("Segoe UI", 9))
        self.lbl_total.pack(side="left")
        self.lbl_prox = tk.Label(linha, text="   |   Proximo: --:--", bg=C_CARD, fg=C_YEL, font=("Segoe UI", 9, "bold"))
        self.lbl_prox.pack(side="left")

        # botoes
        btns = tk.Frame(self.root, bg=C_BG)
        btns.pack(fill="x", padx=20, pady=2)
        self.btn_iniciar = tk.Button(btns, text="▶  Iniciar", command=self._iniciar,
                                     bg=C_GREEN, fg="white", relief="flat", font=("Segoe UI", 12, "bold"),
                                     height=2, cursor="hand2", activebackground="#16a34a")
        self.btn_iniciar.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_parar = tk.Button(btns, text="■  Parar", command=self._parar,
                                   bg=C_RED, fg="white", relief="flat", font=("Segoe UI", 12, "bold"),
                                   height=2, cursor="hand2", state="disabled", activebackground="#b91c1c")
        self.btn_parar.pack(side="left", expand=True, fill="x", padx=(5, 0))

        tk.Label(self.root, text="Registro", bg=C_BG, fg=C_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(10, 0))
        self.txt = scrolledtext.ScrolledText(self.root, height=9, bg=C_LOGBG, fg=C_TXT,
                                             font=("Consolas", 9), relief="flat", state="disabled",
                                             wrap="word", insertbackground="white")
        self.txt.pack(fill="both", expand=True, padx=20, pady=(2, 6))

        tk.Label(self.root, text="Automacao nao-oficial. Use por sua conta e risco.",
                 bg=C_BG, fg=C_GRAY, font=("Segoe UI", 8)).pack(pady=(0, 8))

    # ---- credenciais ----
    def _carregar_credenciais(self):
        if os.path.exists(CRED_PATH):
            try:
                d = json.load(open(CRED_PATH, encoding="utf-8"))
                self.e_email.insert(0, d.get("email", ""))
                self.e_senha.insert(0, d.get("senha", d.get("password", "")))
                self._log("Credenciais carregadas do credenciais.json")
            except Exception as e:
                self._log(f"Nao consegui ler credenciais.json: {e}")
        else:
            self._log("Preencha e-mail e senha e clique em Salvar.")

    def _salvar_credenciais(self, silencioso=False):
        email = self.e_email.get().strip()
        senha = self.e_senha.get().strip()
        try:
            with open(CRED_PATH, "w", encoding="utf-8") as f:
                json.dump({"email": email, "senha": senha}, f, ensure_ascii=False, indent=2)
            self._log("Credenciais salvas em credenciais.json")
            if not silencioso:
                messagebox.showinfo(APP_TITULO, "Credenciais salvas!")
            return True
        except Exception as e:
            if not silencioso:
                messagebox.showerror(APP_TITULO, f"Erro ao salvar: {e}")
            return False

    # ---- controle ----
    def _iniciar(self):
        email = self.e_email.get().strip()
        senha = self.e_senha.get().strip()
        if not email or not senha:
            messagebox.showwarning(APP_TITULO, "Preencha e-mail e senha primeiro.")
            return
        self._salvar_credenciais(silencioso=True)
        self.stop_event.clear()
        self.sessao_abertos = 0
        self.lbl_sessao.config(text="Abertos agora: 0")
        self.btn_iniciar.config(state="disabled")
        self.btn_parar.config(state="normal")
        self.e_email.config(state="disabled")
        self.e_senha.config(state="disabled")
        self.btn_salvar.config(state="disabled")
        self._set_status("on", "Iniciando...")
        self.worker = threading.Thread(target=self._loop, args=(email, senha), daemon=True)
        self.worker.start()

    def _parar(self):
        self._set_status("wait", "Parando apos este passo...")
        self.stop_event.set()
        self.btn_parar.config(state="disabled")

    def _ao_fechar(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel(APP_TITULO, "O robo esta rodando. Parar e sair?"):
                return
            self.stop_event.set()
        self.root.destroy()

    # ---- worker (thread) ----
    def _loop(self, email, senha):
        while not self.stop_event.is_set():
            try:
                tok = login(email, senha)
            except Exception as e:
                self.q.put(("log", f"ERRO no login: {e}"))
                self.q.put(("status", ("off", "Erro no login")))
                self.q.put(("fim", None))
                return
            try:
                st = pack_state(tok)
                self.q.put(("total", st.get("total_packs_opened")))
                self.q.put(("ready", st.get("last_pack_opened")))
                if st.get("is_blocked"):
                    self.q.put(("log", "Conta BLOQUEADA neste album."))
                    self.q.put(("status", ("off", "Conta bloqueada")))
                    self.q.put(("fim", None))
                    return
                self.q.put(("status", ("on", "Tentando abrir...")))
                abertos = 0
                while not self.stop_event.is_set() and abertos < MAX_POR_CICLO:
                    code, data = abrir_um(tok)
                    if code == 200 and not (isinstance(data, dict) and data.get("error")):
                        abertos += 1
                        self.q.put(("abriu", resumo(data)))
                        self.stop_event.wait(1.5)
                    else:
                        if abertos == 0:
                            err = data.get("error") if isinstance(data, dict) else data
                            self.q.put(("log", f"Sem pacote agora: {err}"))
                        break
                try:
                    st = pack_state(tok)
                    self.q.put(("total", st.get("total_packs_opened")))
                    self.q.put(("ready", st.get("last_pack_opened")))
                except Exception:
                    pass
            except Exception as e:
                self.q.put(("log", f"Erro no ciclo: {e}"))

            if self.stop_event.is_set():
                break
            self.q.put(("status", ("on", "Aguardando proximo ciclo")))
            for _ in range(INTERVALO_MIN * 60):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        self.q.put(("status", ("off", "Parado")))
        self.q.put(("fim", None))

    # ---- helpers UI ----
    def _set_status(self, estado, texto):
        cor = {"on": C_GREEN, "off": C_GRAY, "wait": C_YEL}.get(estado, C_GRAY)
        self.lbl_status.config(text=f"●  {texto}", fg=cor)

    def _log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt.config(state="normal")
        self.txt.insert("end", f"[{ts}] {msg}\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _processar_queue(self):
        try:
            while True:
                tipo, val = self.q.get_nowait()
                if tipo == "log":
                    self._log(val)
                    gravar_log(val)
                elif tipo == "abriu":
                    self.sessao_abertos += 1
                    self.lbl_sessao.config(text=f"Abertos agora: {self.sessao_abertos}")
                    self._log(">> " + val)
                    gravar_log(val)
                elif tipo == "total":
                    if val is not None:
                        self.lbl_total.config(text=f"   |   Total no album: {val}")
                elif tipo == "ready":
                    dt = parse_iso(val)
                    if dt:
                        self.next_ready_at = dt + datetime.timedelta(seconds=COOLDOWN)
                elif tipo == "status":
                    self._set_status(val[0], val[1])
                elif tipo == "fim":
                    self.btn_iniciar.config(state="normal")
                    self.btn_parar.config(state="disabled")
                    self.e_email.config(state="normal")
                    self.e_senha.config(state="normal")
                    self.btn_salvar.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(150, self._processar_queue)

    def _tick(self):
        if self.next_ready_at:
            agora = datetime.datetime.now(datetime.timezone.utc)
            restante = (self.next_ready_at - agora).total_seconds()
            if restante <= 0:
                self.lbl_prox.config(text="   |   Proximo: liberado!")
            else:
                m, s = divmod(int(restante), 60)
                self.lbl_prox.config(text=f"   |   Proximo: {m:02d}:{s:02d}")
        self.root.after(1000, self._tick)


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    if os.environ.get("ROBO_SMOKE"):
        root.after(2500, root.destroy)   # teste automatico: fecha sozinho
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            import tkinter.messagebox as mb
            mb.showerror("Robo Caracolada", f"Erro ao iniciar:\n{e}")
        except Exception:
            print("Erro:", e)
