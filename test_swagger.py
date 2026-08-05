import requests
import json
res = requests.get('http://204.168.235.137:2785/api/docs-json')
if res.status_code == 200:
    data = res.json()
    paths = data.get('paths', {}).keys()
    for p in paths:
        if 'message' in p:
            print(p)
else:
    print(res.status_code)
