import requests
import json

url = "http://127.0.0.1:5000/crawl"
data = {"search_query": "aspirin"}

response = requests.post(url, json=data)
print(response.status_code)
results = response.json()

print(json.dumps(results, indent=2))