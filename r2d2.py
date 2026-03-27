print("testando")
from plyer import notification
import pandas as pd
from datetime import datetime, date


compromissos_hoje = 0

notification.notify(
    title="Lembrete",
    message="Entrevista em 30 minutos",
    timeout=10
)

df = pd.read_csv("Agenda.csv")

print(date.today())

for index, row in df.iterrows():
    titulo = row["Titulo"]
    data = row["Data"]
    if data == date.today():
        print(f"{titulo} é hoje!")
        compromissos_hoje+=1
        
    print(data)


