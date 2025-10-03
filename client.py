import requests, json
from mohawk import Sender

creds = {"id":"billard","key":"SUPER_LONG_RANDOM_SECRET","algorithm":"sha256"}
url = "http://127.0.0.1:5000/admin/upload"
data = open("./articles/test.json","rb").read()
sender = Sender(creds, url, "POST", content=data, content_type="application/json")
r = requests.post(url, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": sender.request_header
})
print(r.status_code, r.text)

name = input()

# Test the remove endpoint

url = "http://127.0.0.1:5000/admin/remove"
data = json.dumps({"filename": f"{name}.json"})
sender = Sender(creds, url, "POST", content=data, content_type="application/json")
r = requests.post(url, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": sender.request_header
})
print(r.status_code, r.text)
input()