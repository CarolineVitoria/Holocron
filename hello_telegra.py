import requests
url = "https://api.telegram.org/bot8781352138:AAHSWJsmeZc62i4ojgTnJjWhgaM5NryRRgo/sendMessage"
chat_id = "1211118592"

msg= "Bip-bip... trrrr..."

requests.post(url, data={
    "chat_id": chat_id,
    "text": msg
})