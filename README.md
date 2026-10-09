# Attendly - Employee Attendance Management Portal
Python, Django, HTML, CSS, JavaScript, MySQL.

## 1. Create the MySQL database
Open MySQL (Workbench or terminal) and run:

    CREATE DATABASE attendly_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

## 2. Fill in every "REPLACE WITH YOURS"
* `config/settings.py` -> SECRET_KEY, database NAME, USER, PASSWORD
* `core/management/commands/seed_demo.py` -> DEMO_PASSWORD (password for demo logins)

## 3. Install and run (inside this folder)

    python -m venv venv
    venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
    pip install -r requirements.txt
    python manage.py makemigrations core
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py seed_demo
    python manage.py runserver

Open http://127.0.0.1:8000/

## 4. Try it
* Manager portal: manager1 / your DEMO_PASSWORD
* Employee portal: priyadharshini / your DEMO_PASSWORD
* Manager -> Employees -> ID card shows the QR code. Employee -> Scan -> Start camera
  (or "Scan an image file" with a screenshot of the QR). Each scan toggles check-in / check-out.
* The createsuperuser account is the Admin: it sees all departments and can add managers.
  Manager/Admin pages: Employees, Approvals, Reports, Django admin at /admin/.

Camera scanning works on http://localhost or https only.
