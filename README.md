# CareConnect360: VirtualCare Telemedicine

## Quick start (Windows)
1. `py -3.10 -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `python manage.py makemigrations core && python manage.py migrate`
4. `python manage.py seed_data`
5. `python manage.py runserver`

Demo accounts are printed by `seed_data`: patient `patient1` / `Demo@123456`, doctor `dr.sharma` / `Demo@123456`, admin `admin` / `Admin@123456`.

## Oracle setup
Set environment variables `ORACLE_SERVICE_NAME`, `ORACLE_USER`, and `ORACLE_PASSWORD` to use the configured `django.db.backends.oracle` backend. If Oracle variables are absent, Django uses local SQLite for demos.

Example Oracle DBA setup:
```sql
CREATE USER careconnect IDENTIFIED BY "StrongPassword#123";
GRANT CONNECT, RESOURCE TO careconnect;
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE TO careconnect;
ALTER USER careconnect DEFAULT TABLESPACE users QUOTA UNLIMITED ON users;
```
Install the Oracle Instant Client when thick mode is required; python-oracledb defaults to thin mode when supported. Never commit database passwords. Jitsi is public by default; for production, configure a self-hosted domain and a JWT-authenticated Jitsi deployment and protect JWT secrets through environment variables.

## Security
Private consultation room authorization is enforced server-side for the assigned patient and doctor. Public registration creates patient accounts only; create doctor/admin accounts through Django Admin or a vetted management process. Review DEBUG, SECRET_KEY, TLS, cookies, CSP and host settings before production deployment.
