# DKA demo data and test scenarios

Prepare repeatable demo data from the project folder with:
```powershell
.\venv\Scripts\python.exe manage.py seed_demo_data
```
This keeps existing flights, adds missing flights, and creates media/qrcodes/invalid_demo_qr.png. It does not create users or reset passwords. Existing flight dates and bookings are preserved.

## Scan scenarios
1. Add a test flight from `/admin-panel/flights/add/` with departure between 1 and 24 hours from now in WAT. The six seeded flights are scheduled further ahead and already have bookings, so do not move them for this test. Sign in as a passenger, book the test flight, and check in. Scan its unused boarding pass as staff. Expected: VALID; it becomes used.
2. Scan that same pass again. Expected: ALREADY_USED.
3. Display or print the invalid_demo_qr.png image and scan it. Expected: INVALID.
4. Log in as admin@dka.com and open `/admin-panel/logs/`. Confirm each scan appears with its result and staff account.
5. Confirm admin sees the custom dashboard, gate staff sees the scanner and their own scan history, and passengers see booking links.

## Automated test coverage

Run the full test suite with `.\venv\Scripts\python.exe manage.py test` from the project folder. The current automated tests cover online check-in, QR and PDF creation, gate authentication, VALID, ALREADY USED, INVALID, and EXPIRED scans, staff-only history, admin permissions and management actions, and safe repeated seeding. Passenger registration and the passenger booking flow are manual checks below. The expired-pass case uses a controlled test record because the passenger check-in flow correctly blocks past flights.
