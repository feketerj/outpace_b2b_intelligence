import requests
import time

API = 'http://localhost:8000'

token = requests.post(f'{API}/api/auth/login', json={'email':'admin@example.com','password':'REDACTED_ADMIN_PASSWORD'}).json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

tenant = requests.post(f'{API}/api/tenants', headers=headers, json={'name':'Perf Test','slug':'perf-test'}).json()
tenant_id = tenant['id']
print(f'Created tenant: {tenant_id}')

for i in range(50):
    requests.post(f'{API}/api/opportunities', headers=headers, json={'tenant_id': tenant_id, 'title': f'Opportunity {i}', 'external_id': f'perf-{i}'})
print('Created 50 opportunities')

times = []
for run in range(5):
    start = time.time()
    resp = requests.get(f'{API}/api/opportunities?tenant_id={tenant_id}&per_page=50', headers=headers)
    elapsed = (time.time() - start) * 1000
    count = len(resp.json()['data'])
    times.append(elapsed)
    print(f'Run {run+1}: {elapsed:.1f}ms - {count} opps')

print(f'Average: {sum(times)/len(times):.1f}ms')

requests.delete(f'{API}/api/tenants/{tenant_id}', headers=headers)
print('Cleaned up')
