# Employee Payroll

## Group members

- MAGALA TWAHA
- GUMA RODNEY
- KISUUBIKA SHAFIK

## Requirements

- Python 3.12 or newer
- Dependencies listed in `requirements.txt`

## Local setup

From the project directory, create and activate a virtual environment, then install
the dependencies:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Apply database migrations and create a staff account:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

Start the development server with:

```powershell
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Public signup creates a regular account. Only staff
accounts can access payroll management; create staff accounts through Django admin
or promote trusted accounts from the admin interface.

Staff can create an employee and their login account together from **Employees**.
Provide a unique username and initial password to the employee; they can change
their password after signing in. Employees can view their profile and payslips,
download their own payslip PDFs, update their email and contact number, and submit
leave requests. Staff review and approve or reject leave requests from **Leave
requests**. To link an existing login, edit the employee in **Employees** and
select the account under **Employee login account**.

## Department managers

Payroll staff can assign one active employee login as a department manager from
**Departments → Edit**. The account must already be linked to an employee in that
department, and one account can manage only one department. Managers sign in with
their normal employee account and see department-only employee, leave, payroll
correction, and employee-data review pages. They do not get access to payroll
management or other employees' salary and payslip records; their own employee
self-service remains available.

Employees can submit payroll correction requests. A manager's approval refers the
request to payroll staff; it does not change a payslip or salary. Payroll staff
can review the approved requests and mark them completed. When a department has
an assigned manager, employee profile changes and staff-submitted employee
record changes wait for manager approval. New employee accounts for that
department remain inactive until the manager approves the record. Staff can
review all pending employee-data requests if a manager needs assistance.

## Production settings

Set `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` to a unique secret, and
`DJANGO_ALLOWED_HOSTS` to a comma-separated list of the deployment's host names.
Production mode enables HTTPS redirects, secure session/CSRF cookies, and HSTS.
Configure HTTPS at the deployment proxy before enabling production mode.

The project currently uses SQLite and console email; choose and configure
production database and email services before deploying.

## Render demo deployment

The root `render.yaml` configures a Render web service and PostgreSQL database.
Create a Blueprint from the repository and provide a strong value for the
`DJANGO_SUPERUSER_PASSWORD` secret when prompted. The service migrates the
database, creates the initial `admin` superuser if none exists, and serves
collected static files through WhiteNoise. The local SQLite database is not used
by the deployment.

The Blueprint uses Render's free plans for a demo. Free web services can sleep
when idle, and free PostgreSQL databases expire after 30 days; do not use this
setup for production payroll or long-term data storage.

Employees can download their own payslip PDFs from the employee portal. Staff can
also download PDFs from the payslip register. Employee and payslip registers
include search, filters, and pagination.
