# How to View Different Perspectives - Quick Guide

## Three Ways to View What Users See

---

## Method 1: Preview Button (FASTEST)

**From Admin Panel:**

1. **Login as Super Admin:**
   - Email: `admin@example.com`
   - Password: use the value configured in `SUPER_ADMIN_PASSWORD` or `CARFAX_ADMIN_PASSWORD`

2. **Go to Tenants** (sidebar)

3. **Click "Preview" button** on any tenant card
   - Opens new tab
   - Shows that tenant's white-labeled dashboard
   - No need to logout/login!

4. **Close preview tab** to return to admin panel

**Use this for:** Quick checks of branding, seeing what clients see

---

## Method 2: Login as Tenant User

**Create a tenant user first, then login:**

**Test Account Already Created:**
- **Tenant:** Test Marine Corp
- **Email:** `user@testmarine.com`
- **Password:** use the tenant test password configured in your environment

**Steps:**
1. Logout from admin
2. Login with tenant user credentials
3. See full white-labeled experience
4. Logout when done

**Use this for:** Full testing of tenant features, flows, permissions

---

## Method 3: Create Custom Test Users

**For each tenant you want to test:**

```bash
# Run this Python script to create a user
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from utils.auth import get_password_hash
import os, uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('.env')

async def create_user():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    
    # Get tenant by slug
    tenant = await db.tenants.find_one({'slug': 'YOUR_TENANT_SLUG'})
    
    user = {
        'id': str(uuid.uuid4()),
        'email': 'test@example.com',
        'full_name': 'Test User',
        'role': 'tenant_user',
        'tenant_id': tenant['id'],
        'hashed_password': get_password_hash('password123'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user)
    print('User created!')
    client.close()

asyncio.run(create_user())
"
```

Then login with that user.

---

## What Each Role Sees

### **Super Admin (You)**
- **URL after login:** `/admin`
- **Interface:** OutPace Intelligence admin panel
- **Sidebar:** Dashboard, Tenants, Users
- **Features:**
  - Configure all tenants
  - Manage users
  - System health
  - Preview any tenant view

### **Master Client Admin** (Future)
- **URL after login:** `/master`
- **Interface:** Their white-labeled admin panel
- **Features:**
  - Create their own sub-clients
  - Configure branding for sub-clients
  - View all sub-client data

### **Tenant User (Client)**
- **URL after login:** `/dashboard`
- **Interface:** White-labeled dashboard
- **Branding:** Client's logo + colors
- **Footer:** "Powered by OutPace Intelligence" (or Master Client name if sub-client)
- **Features:**
  - View opportunities (AI-scored)
  - View intelligence reports
  - Sync now button
  - No configuration access
  - No visibility into AI methodology

---

## Quick Testing Workflow

**To test white-labeling:**

1. **Stay logged in as admin**
2. **Configure tenant branding:**
   - Upload logo
   - Set 4 colors
   - Save
3. **Click "Preview"** on that tenant
4. **See:** Their white-labeled dashboard with your branding applied
5. **Close tab**, still in admin panel

**To test full user flow:**

1. **Create tenant user** (or use `user@testmarine.com`)
2. **Logout from admin**
3. **Login as tenant user**
4. **Test features:**
   - View opportunities
   - Click Sync Now
   - Navigate to Intelligence
5. **Logout**
6. **Login back as admin**

---

## Master Client White-Label Testing

**Scenario: Acme Consulting (Master) with Sub-Client XYZ Corp**

**Setup:**
1. Create "Acme Consulting"
   - ☑ Is Master Client
   - Master WL tab: Acme logo + colors
   
2. Create "XYZ Corp"  
   - Basic tab: Normal client
   - Set `master_client_id` to Acme's ID (backend)
   
3. Create user for XYZ Corp

**Test:**
- Login as XYZ Corp user
- **See:** Acme Consulting's logo and colors
- **Footer:** "Powered by Acme Consulting"
- **Not:** OutPace Intelligence

---

## Current Test Accounts

### Super Admin
- Email: `admin@example.com`
- Password: use the value configured in `SUPER_ADMIN_PASSWORD` or `CARFAX_ADMIN_PASSWORD`
- View: Admin panel

### Tenant User (Test Marine Corp)
- Email: `user@testmarine.com`
- Password: use the tenant test password configured in your environment
- View: White-labeled Test Marine dashboard

---

## Recommendations

**Best practice:**
- Use **Preview button** for quick visual checks
- Use **actual tenant login** for full feature testing
- Keep 1-2 test tenant users for each major tenant type

**Next step:** 
I can add a user dropdown in admin panel to "View As" any user without logging out. Would you like that?
