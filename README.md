# Clearway Hospital Appointment Booking System

A Django REST Framework and JavaScript coursework project based on the supplied
hospital appointment booking assignment. Django serves both the frontend and
the API. SQLite stores the local demo data.

## Run locally

Install Python 3.11 or later, extract the ZIP, and open a terminal inside
`hospital-appointments`.

Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Ubuntu or macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The optional seed command creates fictional demo
accounts, specialties, and slots for the next few days. Pick tomorrow to see a
full set of times. The application calendar uses India Standard Time.

| Role | Username | Password |
| --- | --- | --- |
| Patient | `demo_patient` | `ClearwayDemo!26` |
| Doctor (Cardiology) | `demo_cardio` | `ClearwayDemo!26` |
| Doctor (Dermatology) | `demo_skin` | `ClearwayDemo!26` |
| Doctor (Pediatrics) | `demo_child` | `ClearwayDemo!26` |

Create your admin account with `python manage.py createsuperuser`, using your
virtual environment's Python path as shown above. Sign in at
<http://127.0.0.1:8000/admin/>. To add a doctor, add a specialty, create a
regular Django user with an initial password, then link that user to a new
Doctor record. Public registration creates patient accounts.

## Demonstrate the application

1. Browse the directory, filter by specialty, and pick a doctor and a future date.
   Available slots refresh through Fetch without a page reload.
2. Sign in as a patient, choose a slot, enter a reason, and confirm. The
   appointment appears under My appointments and the slot leaves availability.
3. Cancel it at least two hours before the start. The visit remains in history
   as Cancelled and the time becomes bookable again.
4. Sign in as the doctor to view today's and upcoming appointments, create or
   edit an unreserved slot, and try adding an overlapping slot. Once an
   appointment starts, the doctor can mark it Completed with optional notes.
   Slots with any appointment history are kept so past records retain their
   scheduled time. Completed and cancelled visits are final.
5. Use Django Admin to manage specialties and doctor accounts and inspect
   the slot and appointment records.

## API and booking rules

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/session/` | Current account role |
| POST | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/logout/` | Session actions |
| GET | `/api/directory/?specialty=ID` | Doctor directory, optional filter |
| GET | `/api/availability/?doctor=ID&date=YYYY-MM-DD` | Available slots |
| GET, POST | `/api/doctor/slots/` | List or create your slots |
| PUT, DELETE | `/api/doctor/slots/ID/` | Edit or delete your slots |
| POST | `/api/appointments/` | Book a slot with a visit reason |
| POST | `/api/appointments/ID/cancel/` | Cancel your appointment |
| POST | `/api/appointments/ID/complete/` | Complete a visit with optional notes |
| GET | `/api/dashboard/` | Role-specific appointment lists |

The browser uses Django session cookies and sends a CSRF token with write
requests. Server-side role and ownership checks protect patient and doctor
records. SQLite immediate transactions serialize schedule changes and
bookings. Two partial unique constraints protect against duplicate
reservations for the same slot and duplicate appointments for the same
patient at the exact same date and start time. A competing booking receives
HTTP 409. Cancelled records remain in history and are excluded from these
constraints.

## Tests and source layout

Run `python manage.py test --noinput` using the virtual environment's Python.
The suite covers simultaneous booking, cancellation and reopening, completion,
duplicate patient times, slot validation, role checks, and CSRF.

- `hospital/` contains settings and routes.
- `booking/` contains the models, API, admin configuration, migrations, and tests.
- `booking/static/booking/` contains the frontend JavaScript and CSS.
- `booking/templates/booking/` contains the page shell.

The included settings and seed accounts are intended for a local coursework demo.
