#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Robo Caracolada - versao NUVEM (GitHub Actions). Roda UMA vez por execucao;
o agendamento (cron) cuida de repetir. Abre o pacote do album Copa SPC Brasil 2026.

Credenciais vem das variaveis de ambiente (GitHub Secrets):
    CARACOLADA_EMAIL  e  CARACOLADA_SENHA
A senha NUNCA fica no codigo nem e impressa nos logs.
"""
import os
import sys
import time
import datetime
import requests

# --- config publica (igual p/ todos; nao e segredo) ---
SUPA = "https://wbyuabdjxtgbzylgbrom.supabase.co"
ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndieXVhYmRqeHRnYnp5bGdicm9tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkwMjEzMTIsImV4cCI6MjA4NDU5NzMxMn0._b3As42NjpPjB1Twq6lfIiZHtvBMUXUKKVRCDGLdOXY"
ALBUM = "b93ee3a6-6a36-4dc0-aaa6-53b28fd9f412"
COOLDOWN = 900          # 15 min
MAX_POR_EXEC = 25

EMAIL = os.environ.get("CARACOLADA_EMAIL", "").strip()
SENHA = os.environ.get("CARACOLADA_SENHA", "").strip()


def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def login():
    r = requests.post(
        f"{SUPA}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON, "Content-Type": "application/json"},
        json={"email": EMAIL, "password": SENHA},
        timeout=30,
    )
    if r.status_code != 200:
        # nao imprime o corpo (pode conter dados sensiveis)
        raise RuntimeError(f"login falhou (HTTP {r.status_code})")
    return r.json()["access_token"]


def _h(t):
    return {"apikey": ANON, "Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def pack_state(t):
    r = requests.post(f"{SUPA}/rest/v1/rpc/get_my_album_pack_state",
                      headers=_h(t), json={"_album_id": ALBUM}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})


def abrir_um(t):
    r = requests.post(f"{SUPA}/functions/v1/open-pack",
                      headers=_h(t), json={"albumId": ALBUM}, timeout=40)
    try:
        data = r.json()
    except Exception:
        data = {"error": f"HTTP {r.status_code}"}
    return r.status_code, data


def resumo(data):
    fig = data.get("stickers") or []
    its = [f"#{s.get('number')} {s.get('name', '?')}" for s in fig if isinstance(s, dict)]
    return (f"{len(fig)} figurinha(s): " + "; ".join(its)) if its else "pacote aberto"


def cooldown_vencido(last_iso):
    if not last_iso:
        return True, 0
    try:
        last = datetime.datetime.fromisoformat(str(last_iso).replace("Z", "+00:00"))
    except Exception:
        return True, 0
    falta = COOLDOWN - (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
    return (falta <= 0), max(0, int(falta))


def main():
    if not EMAIL or not SENHA:
        log("ERRO: defina os Secrets CARACOLADA_EMAIL e CARACOLADA_SENHA no GitHub.")
        sys.exit(1)

    tok = login()
    log("login OK")

    st = pack_state(tok)
    if st.get("is_blocked"):
        log("conta BLOQUEADA neste album. Abortando.")
        return
    extra = int(st.get("packets_balance", 0) or 0) + int(st.get("extra_packs_balance", 0) or 0)
    venceu, falta = cooldown_vencido(st.get("last_pack_opened"))
    log(f"estado: extras={extra} | cooldown_vencido={venceu} (faltam {falta}s) | total_aberto={st.get('total_packs_opened')}")

    # so chama o open-pack se ha o que abrir (evita marteladas inuteis no servidor)
    if not venceu and extra <= 0:
        log(f"nada para abrir agora (proximo pacote em ~{falta}s).")
        return

    abertos = 0
    while abertos < MAX_POR_EXEC:
        code, data = abrir_um(tok)
        err = data.get("error") if isinstance(data, dict) else None
        if code == 200 and not err:
            abertos += 1
            msg = f"  pacote #{abertos}: {resumo(data)}"
            if data.get("prize"):
                msg += f" | PREMIO: {data.get('prize')}"
            log(msg)
            time.sleep(1.5)
        else:
            log(f"  sem mais pacote: {err}")
            break
    log(f"fim: {abertos} pacote(s) aberto(s) nesta execucao.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERRO: {e}")
        sys.exit(1)
