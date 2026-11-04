# Trunemo

Trunemo is a Django web app for tracking event guests, gifts, and split payments. Each account has its own events. The dashboard and Excel export calculate totals from payments.

## Run locally in VS Code

Open the project folder and choose **Terminal → New Terminal**. If the existing `.venv` is available, start with the installation command below. For a fresh checkout, create it first with `py -3.12 -m venv .venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011
```

Open [Trunemo](http://127.0.0.1:8011/). Create an account, add an event and a guest group, then add guests. **Add gift** records the first payment. Use **Add payment** on the gift page for each additional part. **Export Excel** is on the event page.

## Use PostgreSQL and DBeaver

Create an empty PostgreSQL database named `giftmanager` in DBeaver using a PostgreSQL role with permission to create databases. Use the same role for local development, or give your development role permission to create tables in the database.

Set the connection details in the VS Code PowerShell terminal. Use your actual PostgreSQL role and password.

```powershell
$env:POSTGRES_DB = "giftmanager"
$env:POSTGRES_USER = "your_postgres_role"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
$credential = Get-Credential -UserName $env:POSTGRES_USER -Message "PostgreSQL login"
$env:POSTGRES_PASSWORD = $credential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011
```

Set these variables in each new terminal that should use PostgreSQL. When `POSTGRES_DB` is unset, the app uses the local SQLite file. Each database has its own users and events. On a new database, create an account from the homepage after running migrations.

In DBeaver, connect to the same database. After recording a gift and payments, run this query to see how the app's gift total relates to the stored rows.

```sql
SELECT g.id, g.description, COALESCE(SUM(p.amount), 0) AS total_received
FROM events_gift AS g
LEFT JOIN events_payment AS p ON p.gift_id = g.id
GROUP BY g.id, g.description
ORDER BY g.id;
```

## Code map

- `events/models.py` defines the database tables and relationships. `GiftRecipient` links a gift to its recipients, and `Payment` links a payer and amount to a gift.
- `events/forms.py` validates input. Recipients are selected from the gift's group, and payers can be any guest in the event.
- `events/views.py` handles requests and limits event access to the signed-in owner.
- `events/queries.py` uses the Django ORM to search and sum payments.
- `events/exports.py` builds the Excel workbook with a summary, gifts, and payments.
- `templates/` and `events/static/` contain the HTML and CSS.

## Verify

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

When running tests with PostgreSQL, use a role with permission to create a separate test database.

## Share a hosted prototype

1. Create a free Neon PostgreSQL project named `trunemo`. In Neon, open **Connect** and copy the direct connection string with connection pooling turned off.
2. Put the project source in a private GitHub repository with `render.yaml` at its root. Keep local databases and secrets out of Git.
3. In Render, choose **New → Blueprint** and connect that repository. Paste the Neon connection string into the `DATABASE_URL` field in Render. Render generates the Django secret.
4. Open the deployed HTTPS URL, create a demo account with fictional data, and check event creation and Excel export before sharing the link.

The first visit after the free web service goes idle can take about a minute.
