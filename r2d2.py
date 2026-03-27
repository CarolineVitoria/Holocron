print("testando")
from plyer import notification
import pandas as pd
from datetime import datetime, date
import schedule
import time


qtd_compromissos_hoje = 0
RELATORIO_ENVIADO = True

notification.notify(
    title="Lembrete",
    message="Entrevista em 30 minutos",
    timeout=10
)

df = pd.read_csv("Agenda.csv")

print(date.today())

for index, row in df.iterrows():
    hoje = datetime.today().strftime('%Y-%M-%D')
    titulo = row["Titulo"]
    data = row["Data"]
    if data == date.today():
        print(f"{titulo} é hoje!")
        qtd_compromissos_hoje+=1

        
    print(data)
def enviaRelatorio():
    print("Envia Relatório")

def criaRelatorio():
    print("relatório criado")
    enviaRelatorio()

def relatorioDiario():
    if not RELATORIO_ENVIADO:
        criaRelatorio()
    else:
        print("aaaa")
        

while True:
    time.sleep(12)
    schedule.every().day.at("17:29").do(criaRelatorio)

    relatorioDiario()

