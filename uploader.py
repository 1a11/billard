import requests, json
from mohawk import Sender

creds = {
    "id":"billard",
    "key":"CHANGE_ME",
    "algorithm":"sha256"
}
url = "http://SERVER_IP:666/admin/upload"
data = open("./articles/PAGE_NAME.json","rb").read()


sender = Sender(creds, url, "POST", content=data, content_type="application/json")
r = requests.post(url, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": sender.request_header
})
print(r.status_code, r.text)

# Test the remove endpoint
name = input()

url = "http://SERVER_IP:666/admin/remove"
data = json.dumps({"filename": f"{name}.json"})
sender = Sender(creds, url, "POST", content=data, content_type="application/json")
r = requests.post(url, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": sender.request_header
})
print(r.status_code, r.text)
input()