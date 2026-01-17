# UI TEST PLAN

**Created:** 2026-01-12
**Frontend URL:** http://localhost:3000
**Backend URL:** http://localhost:8000

---

## TEST CREDENTIALS

| Role | Email | Password |
|------|-------|----------|
| Super Admin | admin@outpace.ai | Admin123! |
| Tenant User | (create via Super Admin) | (set during creation) |

---

## PRE-TEST CHECKLIST

- [ ] Docker Desktop running
- [ ] MongoDB container started: `docker start mongo-b2b`
- [ ] Backend running: `cd backend && python -m uvicorn server:app --reload --port 8000`
- [ ] Frontend running: `cd frontend && npm start`
- [ ] Browser open to http://localhost:3000

---

## TEST MATRIX

### 1. LOGIN PAGE (http://localhost:3000/login)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| L1 | Page loads | Navigate to /login | Login form visible with email/password fields | [ ] |
| L2 | Empty submit | Click Sign In with empty fields | Validation error, no submission | [ ] |
| L3 | Invalid email | Enter "notanemail", valid password | Validation error on email format | [ ] |
| L4 | Wrong credentials | Enter wrong email/password | Toast error "Invalid credentials" | [ ] |
| L5 | Successful login (Super Admin) | admin@outpace.ai / Admin123! | Redirect to /admin dashboard | [ ] |
| L6 | Successful login (Tenant User) | Tenant user credentials | Redirect to /dashboard | [ ] |
| L7 | Loading state | Click Sign In with valid creds | Button shows "Signing in..." | [ ] |
| L8 | Already logged in | Navigate to /login while authenticated | Redirect to appropriate dashboard | [ ] |

### 2. SUPER ADMIN DASHBOARD (http://localhost:3000/admin)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| SA1 | Page access | Login as super admin | Dashboard displays system overview | [ ] |
| SA2 | Tenant count | View dashboard | Shows total tenant count | [ ] |
| SA3 | Navigate to Tenants | Click Tenants nav item | Navigates to /admin/tenants | [ ] |
| SA4 | Navigate to Users | Click Users nav item | Navigates to /admin/users | [ ] |
| SA5 | Logout | Click logout button | Clears session, redirects to /login | [ ] |
| SA6 | Unauthorized access | Navigate while logged out | Redirect to /login | [ ] |

### 3. TENANT MANAGEMENT (http://localhost:3000/admin/tenants)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| TM1 | List tenants | Navigate to page | Table displays all tenants | [ ] |
| TM2 | Search tenants | Enter search query | Table filters by tenant name | [ ] |
| TM3 | Create tenant button | Click "Add Tenant" | Modal/form opens | [ ] |
| TM4 | Create tenant - required fields | Leave name empty | Validation error | [ ] |
| TM5 | Create tenant - success | Fill all required fields, submit | Tenant created, appears in list | [ ] |
| TM6 | Edit tenant | Click edit on existing tenant | Edit form opens with data | [ ] |
| TM7 | Edit tenant - save | Modify name, save | Changes persist, toast success | [ ] |
| TM8 | Delete tenant | Click delete, confirm | Tenant removed from list | [ ] |
| TM9 | Delete tenant - cancel | Click delete, cancel | Tenant remains | [ ] |
| TM10 | Branding - logo upload | Upload logo image | Logo preview displays | [ ] |
| TM11 | Branding - primary color | Use color picker | Color preview updates | [ ] |
| TM12 | Branding - secondary color | Use color picker | Color preview updates | [ ] |
| TM13 | Branding - save | Save branding changes | Changes persist | [ ] |
| TM14 | Preview tenant view | Click preview button | Opens tenant-branded preview | [ ] |
| TM15 | Pagination | Create 20+ tenants | Pagination controls work | [ ] |

### 4. USER MANAGEMENT (http://localhost:3000/admin/users)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| UM1 | List users | Navigate to page | Table displays all users | [ ] |
| UM2 | Filter by tenant | Select tenant filter | Only that tenant's users shown | [ ] |
| UM3 | Create user button | Click "Add User" | Modal/form opens | [ ] |
| UM4 | Create user - required fields | Leave email empty | Validation error | [ ] |
| UM5 | Create user - invalid email | Enter invalid email format | Validation error | [ ] |
| UM6 | Create user - success | Fill all required fields, submit | User created, appears in list | [ ] |
| UM7 | Create user - select tenant | Choose tenant for user | User associated with tenant | [ ] |
| UM8 | Create user - select role | Choose role | Role assigned correctly | [ ] |
| UM9 | Edit user | Click edit on existing user | Edit form opens with data | [ ] |
| UM10 | Edit user - change role | Change role, save | Role updated | [ ] |
| UM11 | Delete user | Click delete, confirm | User removed from list | [ ] |
| UM12 | Reset password | Click reset password | New password generated/sent | [ ] |

### 5. TENANT DASHBOARD (http://localhost:3000/dashboard)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| TD1 | Page access | Login as tenant user | Dashboard displays opportunity grid | [ ] |
| TD2 | Stats cards | View dashboard | Total, High Priority, Last Updated cards show | [ ] |
| TD3 | Search opportunities | Enter search query | Grid filters by title/description | [ ] |
| TD4 | Opportunity card display | View grid | Cards show title, score, description, metadata | [ ] |
| TD5 | Score badge colors | View cards with different scores | 75+ green, 50-74 blue, <50 gray | [ ] |
| TD6 | AI summary display | View card with AI summary | AI analysis section visible | [ ] |
| TD7 | Click opportunity | Click on opportunity card | Navigates to /opportunities/:id | [ ] |
| TD8 | Manual sync button | Click "Sync Now" | Sync starts, shows progress | [ ] |
| TD9 | Export button | Click Export | Export modal opens | [ ] |
| TD10 | Empty state | View with no opportunities | "No opportunities yet" message | [ ] |
| TD11 | Loading state | Refresh page | Loading indicator shows | [ ] |
| TD12 | Tenant branding | View dashboard | Tenant primary color applied | [ ] |

### 6. OPPORTUNITY DETAIL (http://localhost:3000/opportunities/:id)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| OD1 | Page access | Click opportunity from grid | Detail view displays | [ ] |
| OD2 | All fields display | View detail | Title, description, agency, due date, value visible | [ ] |
| OD3 | Score display | View detail | Score badge with color coding | [ ] |
| OD4 | AI analysis display | View detail | AI relevance summary shown | [ ] |
| OD5 | Status selector | View status dropdown | Current status selected | [ ] |
| OD6 | Change status | Select different status | Status updates, toast success | [ ] |
| OD7 | Add note | Enter note, save | Note appears in notes section | [ ] |
| OD8 | Edit note | Edit existing note | Note updated | [ ] |
| OD9 | Delete note | Delete note | Note removed | [ ] |
| OD10 | Add tag | Add tag to opportunity | Tag appears | [ ] |
| OD11 | Remove tag | Remove tag | Tag removed | [ ] |
| OD12 | Back navigation | Click back | Returns to dashboard | [ ] |
| OD13 | Archive opportunity | Click archive | Opportunity archived | [ ] |
| OD14 | Unarchive opportunity | Click unarchive | Opportunity restored | [ ] |

### 7. INTELLIGENCE FEED (http://localhost:3000/intelligence)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| IF1 | Page access | Navigate to Intelligence | Feed displays AI reports | [ ] |
| IF2 | Report list | View feed | Reports listed with titles/dates | [ ] |
| IF3 | Filter by type | Select report type | Feed filters | [ ] |
| IF4 | View report | Click report | Full report displays | [ ] |
| IF5 | Generate report | Click generate | New report created | [ ] |
| IF6 | Delete report | Delete report | Report removed | [ ] |
| IF7 | Empty state | View with no reports | "No intelligence reports" message | [ ] |

### 8. CHAT ASSISTANT (Overlay on all pages)

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| CA1 | Chat bubble visible | View any page | Chat bubble in bottom-right | [ ] |
| CA2 | Open chat | Click chat bubble | Chat panel expands | [ ] |
| CA3 | Close chat | Click close/X | Chat panel closes | [ ] |
| CA4 | Send message | Type message, send | Message appears in chat | [ ] |
| CA5 | Receive response | After sending | AI response appears | [ ] |
| CA6 | Typing indicator | While AI responding | Typing indicator shows | [ ] |
| CA7 | Message history | Send multiple messages | History maintained | [ ] |
| CA8 | Clear chat | Click clear | History cleared | [ ] |
| CA9 | Quota limit | Exceed quota | Error message about limit | [ ] |
| CA10 | Branding color | View chat | Uses tenant primary color | [ ] |

### 9. EXPORT MODAL

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| EX1 | Open modal | Click Export button | Modal opens | [ ] |
| EX2 | Close modal | Click outside/X | Modal closes | [ ] |
| EX3 | Select all | Click select all | All opportunities selected | [ ] |
| EX4 | Deselect all | Click deselect all | All deselected | [ ] |
| EX5 | Individual select | Click checkbox | Individual item selected | [ ] |
| EX6 | PDF format | Select PDF, export | PDF file downloads | [ ] |
| EX7 | Excel format | Select Excel, export | Excel file downloads | [ ] |
| EX8 | Export progress | During export | Progress indicator shows | [ ] |
| EX9 | Export success | After export | Success toast | [ ] |
| EX10 | No selection error | Export with nothing selected | Error message | [ ] |
| EX11 | Branded export | Export PDF | Tenant logo/colors in file | [ ] |

### 10. NAVIGATION & LAYOUT

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| NV1 | Sidebar visibility | View on desktop | Sidebar always visible | [ ] |
| NV2 | Active nav item | Navigate pages | Active page highlighted | [ ] |
| NV3 | Mobile menu | View on mobile | Hamburger menu shows | [ ] |
| NV4 | Mobile menu toggle | Click hamburger | Menu opens/closes | [ ] |
| NV5 | Logo click | Click logo | Navigates to dashboard | [ ] |
| NV6 | User menu | Click user avatar | Dropdown shows | [ ] |
| NV7 | Logout from menu | Click logout in menu | Session ends, redirect | [ ] |

### 11. ACCESSIBILITY

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| A1 | Keyboard navigation | Tab through page | Focus visible on all elements | [ ] |
| A2 | Enter to submit | Press Enter in form | Form submits | [ ] |
| A3 | Escape to close | Press Escape in modal | Modal closes | [ ] |
| A4 | Screen reader labels | Use screen reader | All elements have labels | [ ] |
| A5 | Color contrast | Use contrast checker | All text meets WCAG AA | [ ] |
| A6 | Focus trap in modal | Tab in modal | Focus stays in modal | [ ] |

### 12. ERROR HANDLING

| ID | Test Case | Steps | Expected Result | Status |
|----|-----------|-------|-----------------|--------|
| E1 | API timeout | Simulate slow network | Loading state, then error | [ ] |
| E2 | 401 response | Token expires mid-session | Redirect to login | [ ] |
| E3 | 403 response | Access denied resource | Error message shown | [ ] |
| E4 | 404 response | Navigate to bad URL | 404 page shown | [ ] |
| E5 | 500 response | Server error | Generic error message (no stack) | [ ] |
| E6 | Network offline | Disconnect network | Offline indicator | [ ] |

---

## BROWSER COMPATIBILITY

Test in:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Edge (latest)
- [ ] Safari (latest) - if Mac available

---

## RESPONSIVE BREAKPOINTS

Test each page at:
- [ ] Mobile (320px)
- [ ] Tablet (768px)
- [ ] Desktop (1280px)
- [ ] Large Desktop (1920px)

---

## DATA TEST IDS

All interactive elements should have `data-testid` attributes for automated testing:

```
data-testid="login-form"
data-testid="login-email-input"
data-testid="login-password-input"
data-testid="login-submit-button"
data-testid="manual-sync-button"
data-testid="opportunity-card-{id}"
data-testid="export-button"
data-testid="chat-bubble"
data-testid="chat-panel"
data-testid="chat-input"
data-testid="chat-send-button"
```

---

## NOTES

- Run backend preflight: `python scripts/doctor.py`
- Run backend tests: `pytest backend/tests/ -v`
- Clear localStorage if login issues: `localStorage.clear()` in browser console

---

## VERSION HISTORY

| Date | Change |
|------|--------|
| 2026-01-12 | Initial test plan created |
