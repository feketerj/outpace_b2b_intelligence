import os
import requests
import time

API = 'http://localhost:8000'

admin_email = os.environ["CARFAX_ADMIN_EMAIL"]
admin_password = os.environ["CARFAX_ADMIN_PASSWORD"]
token = requests.post(f'{API}/api/auth/login', json={'email': admin_email, 'password': admin_password}).json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

tenant = requests.post(f'{API}/api/tenants', headers=headers, json={'name':'Diag Test','slug':'diag-test'}).json()
tenant_id = tenant['id']
print(f'Tenant: {tenant_id}')

# Create ONE opp and check response
print('Creating 1 opportunity...')
resp = requests.post(f'{API}/api/opportunities', headers=headers, json={'tenant_id': tenant_id, 'title': 'Test Opp', 'external_id': 'diag-1'})
print(f'Create status: {resp.status_code}')
print(f'Create response: {resp.text[:500]}')

# Check DB directly
from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017')['outpace_intelligence']
count = db.opportunities.count_documents({'tenant_id': tenant_id})
print(f'DB count for tenant: {count}')

# List via API - time it
print('Listing via API...')
start = time.time()
resp = requests.get(f'{API}/api/opportunities?tenant_id={tenant_id}&per_page=50', headers=headers)
elapsed = (time.time() - start) * 1000
print(f'List status: {resp.status_code}')
print(f'List time: {elapsed:.0f}ms')
print(f'List count: {len(resp.json().get("data", []))}')
print(f'List response: {resp.text[:500]}')

# Cleanup
db.opportunities.delete_many({'tenant_id': tenant_id})
db.tenants.delete_one({'id': tenant_id})
print('Cleaned up')
