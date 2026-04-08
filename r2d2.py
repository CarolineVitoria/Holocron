import pandas as pd
import schedule
import time
import requests
import os
import sys
from datetime import datetime, date, timedelta
from plyer import notification
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import locale

locale.setlocale(locale.LC_TIME, "Portuguese_Brazil.1252")

load_dotenv()

TELEGRAM_TOKEN     = os.getenv("TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("CHAT_ID")
SHEETS_URL         = os.getenv("SHEETS_URL")  
HORA_RELATORIO     = "08:00"

notificacoes_enviadas  = set()
relatorio_enviado_hoje = None

def carregar_agenda():
    if not SHEETS_URL:
        print("[ERRO] Configure SHEETS_URL no .env")
        sys.exit(1)

    print("[RPA] Abrindo Google Sheets com Playwright...")
    registros = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page    = browser.new_page()
        page.goto(SHEETS_URL, wait_until="networkidle", timeout=30000)

        frame = None
        for f in page.frames:
            if "sheet?headers=false" in f.url:
                frame = f
                break

        if not frame:
            print("[ERRO] Frame da planilha não encontrado.")
            browser.close()
            sys.exit(1)

        # Aguarda a tabela waffle carregar dentro do frame
        frame.wait_for_selector("table.waffle", timeout=20000)

        linhas = frame.query_selector_all("table.waffle tbody tr")
        print(f"[DEBUG] {len(linhas)} linhas encontradas na tabela.")

        cabecalho_pulado = False
        for linha in linhas:
            celulas = linha.query_selector_all("td")
            valores = [c.inner_text().strip() for c in celulas]

            if not any(valores):
                continue

            if not cabecalho_pulado:
                cabecalho_pulado = True
                continue

            while len(valores) < 4:
                valores.append("")

            titulo, data_str, hora_str, descricao = (
                valores[0], valores[1], valores[2], valores[3]
            )

            if not titulo or not data_str or not hora_str:
                continue

            registros.append({
                "Titulo":    titulo,
                "Data":      data_str,
                "Hora":      hora_str,
                "Descricao": descricao,
            })

        browser.close()

    print(f"[RPA] {len(registros)} tarefa(s) extraída(s) da planilha.")

    if not registros:
        return pd.DataFrame(columns=["Titulo", "Data", "Hora", "Descricao", "DataHora"])

    df = pd.DataFrame(registros)
    df["DataHora"] = pd.to_datetime(
        df["Data"] + " " + df["Hora"],
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    df = df.dropna(subset=["DataHora"])
    return df
def _carregar_via_csv_export():
    """
    Fallback: converte a URL pubhtml para exportação direta em CSV.
    Ex: /spreadsheets/d/ID/pubhtml → /spreadsheets/d/ID/export?format=csv
    """
    import re
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", SHEETS_URL)
    if not match:
        print("[ERRO] Não foi possível extrair o ID da planilha da URL.")
        sys.exit(1)

    sheet_id  = match.group(1)
    csv_url   = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    print(f"[RPA] Baixando CSV de: {csv_url}")

    df = pd.read_csv(csv_url)
    df.columns = [c.strip() for c in df.columns]

    df["DataHora"] = pd.to_datetime(
        df["Data"].astype(str) + " " + df["Hora"].astype(str),
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )
    df = df.dropna(subset=["DataHora"])
    print(f"[CSV] {len(df)} tarefa(s) carregada(s).")
    return df

def tocar_som():
    if sys.platform == "win32":
        import winsound
        for _ in range(3):
            winsound.Beep(1000, 300)
            time.sleep(0.1)
    elif sys.platform == "darwin":
        os.system("afplay /System/Library/Sounds/Glass.aiff")
    else:
        if os.system("paplay /usr/share/sounds/freedesktop/stereo/bell.oga 2>/dev/null") != 0:
            if os.system("aplay /usr/share/sounds/alsa/Front_Left.wav 2>/dev/null") != 0:
                print("\a")


def notificar(titulo, mensagem):
    try:
        notification.notify(
            title=titulo,
            message=mensagem,
            app_name="Agenda",
            timeout=15,
        )
    except Exception as e:
        print(f"[AVISO] Notificação desktop falhou: {e}")
    tocar_som()


def verificar_tarefas():
    df    = carregar_agenda()
    agora = datetime.now()

    for _, row in df.iterrows():
        tarefa_dt    = row["DataHora"]
        diff_minutos = (tarefa_dt - agora).total_seconds() / 60

        if 0 <= diff_minutos <= 65:
            chave = f"{row['Titulo']}_{tarefa_dt}"
            if chave not in notificacoes_enviadas:
                titulo_notif = f"⏰ Em ~1 hora: {row['Titulo']}"
                msg = (f"Às {tarefa_dt.strftime('%H:%M')} — "
                       f"{row.get('Descricao', 'Sem descrição')}")
                print(f"[NOTIFICAÇÃO] {titulo_notif} | {msg}")
                notificar(titulo_notif, msg)
                notificacoes_enviadas.add(chave)


def enviar_telegram(mensagem: str):
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       mensagem,
        "parse_mode": "Markdown",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("[TELEGRAM] Mensagem enviada com sucesso.")
    except requests.RequestException as e:
        print(f"[ERRO] Falha ao enviar para o Telegram: {e}")


def gerar_relatorio():
    global relatorio_enviado_hoje
    hoje = date.today()

    if relatorio_enviado_hoje == hoje:
        return

    df       = carregar_agenda()
    limite   = datetime.combine(hoje + timedelta(days=7), datetime.max.time())
    inicio   = datetime.combine(hoje, datetime.min.time())
    proximas = df[(df["DataHora"] >= inicio) & (df["DataHora"] <= limite)].sort_values("DataHora")

    linhas = [
        f"📅 *Relatório — {hoje.strftime('%d/%m/%Y')}*",
        f"Suas tarefas nos próximos 7 dias:\n",
    ]

    if proximas.empty:
        linhas.append("_Nenhuma tarefa agendada para os próximos 7 dias._ 🎉")
    else:
        dia_atual = None
        for _, row in proximas.iterrows():
            dia = row["DataHora"].date()
            if dia != dia_atual:
                label = "Hoje" if dia == hoje else row["DataHora"].strftime("%A, %d/%m")
                linhas.append(f"\n*{label}*")
                dia_atual = dia
            hora      = row["DataHora"].strftime("%H:%M")
            descricao = row.get("Descricao", "")
            desc_str  = f" — {descricao}" if pd.notna(descricao) and descricao else ""
            linhas.append(f"  • {hora} › {row['Titulo']}{desc_str}")

    mensagem = "\n".join(linhas)
    print("\n" + mensagem + "\n")
    enviar_telegram(mensagem)
    relatorio_enviado_hoje = hoje


def iniciar():
    print("=" * 50)
    print("  Agenda Inteligente — iniciada")
    print("  Fonte: Google Sheets via Playwright (RPA)")
    print(f"  Relatório diário às {HORA_RELATORIO}")
    print("=" * 50)

    df = carregar_agenda()
    print(f"[INFO] {len(df)} tarefa(s) carregada(s).\n")

    schedule.every(1).minutes.do(verificar_tarefas)
    schedule.every().day.at(HORA_RELATORIO).do(gerar_relatorio)

    gerar_relatorio()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    iniciar()