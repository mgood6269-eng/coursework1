import os
from calendar import monthrange
from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc

# ----------------------------------------
# Flask
# ----------------------------------------
app = Flask(__name__, template_folder="templates")
app.secret_key = "super_secret_key"

# ----------------------------------------
# Подключение к SQL Server
# ----------------------------------------
def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=Ayat\\SQLEXPRESS;"       # <-- твой сервер
        "DATABASE=EmployeesDB;"          # <-- твоя база
        "Trusted_Connection=yes;"        # <-- Windows Auth
    )
    return pyodbc.connect(conn_str)

# ----------------------------------------
# Форматирование месяца "Февраль 2025"
# ----------------------------------------
def format_month(date_obj):
    if not date_obj:
        return "-"

    months = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    m = date_obj.month
    y = date_obj.year
    return f"{months[m]} {y}"

# Делаем функцию доступной в шаблонах
app.jinja_env.globals.update(format_month=format_month)

# ----------------------------------------
# Главная — список сотрудников
# ----------------------------------------
@app.route("/")
def index():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.employee_id, e.first_name, e.last_name, e.phone,
               p.title AS position_name,
               d.name AS department_name
        FROM Employee e
        LEFT JOIN Position p ON e.position_id = p.position_id
        LEFT JOIN Department d ON e.department_id = d.department_id
        ORDER BY e.employee_id
    """)

    employees = cur.fetchall()
    conn.close()
    return render_template("employees.html", employees=employees)

# ----------------------------------------
# Добавить сотрудника
# ----------------------------------------
@app.route("/employee/add", methods=["GET", "POST"])
def add_employee():
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            INSERT INTO Employee (first_name, last_name, birth_date, phone, email,
                                  hire_date, position_id, department_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        request.form.get("first_name"),
        request.form.get("last_name"),
        request.form.get("birth_date") or None,
        request.form.get("phone"),
        request.form.get("email"),
        request.form.get("hire_date") or None,
        request.form.get("position_id"),
        request.form.get("department_id")
        )

        conn.commit()
        conn.close()
        flash("Сотрудник добавлен!", "success")
        return redirect(url_for("index"))

    cur.execute("SELECT position_id, title FROM Position ORDER BY position_id")
    positions = cur.fetchall()

    cur.execute("SELECT department_id, name FROM Department ORDER BY department_id")
    departments = cur.fetchall()

    conn.close()
    return render_template("add_employee.html", positions=positions, departments=departments)

# ----------------------------------------
# Добавить зарплату (только месяц)
# ----------------------------------------
@app.route("/employee/<int:id>/salary/add", methods=["GET", "POST"])
def add_salary(id):
    if request.method == "POST":
        amount = request.form.get("amount")
        salary_month = request.form.get("salary_month")  # формат YYYY-MM

        if not amount or not salary_month:
            flash("Заполните все поля!", "error")
            return redirect(url_for("add_salary", id=id))

        year, month = map(int, salary_month.split("-"))

        # первый день месяца
        from_date = f"{year}-{month:02d}-01"

        # последний день месяца
        last_day = monthrange(year, month)[1]
        to_date = f"{year}-{month:02d}-{last_day:02d}"

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Salary (employee_id, amount, from_date, to_date)
            VALUES (?, ?, ?, ?)
        """, id, amount, from_date, to_date)

        conn.commit()
        conn.close()
        flash("Зарплата добавлена!", "success")
        return redirect(url_for("view_employee", id=id))

    return render_template("add_salary.html", employee_id=id)

# ----------------------------------------
# Добавить отпуск
# ----------------------------------------
@app.route("/employee/<int:id>/vacation/add", methods=["GET", "POST"])
def add_vacation(id):
    if request.method == "POST":
        start = request.form.get("from_date")
        end = request.form.get("to_date")

        if not start or not end:
            flash("Заполните даты!", "error")
            return redirect(url_for("add_vacation", id=id))

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Vacation (employee_id, start_date, end_date)
            VALUES (?, ?, ?)
        """, id, start, end)

        conn.commit()
        conn.close()
        flash("Отпуск добавлен!", "success")
        return redirect(url_for("view_employee", id=id))

    return render_template("add_vacation.html", employee_id=id)

# ----------------------------------------
# Карточка сотрудника
# ----------------------------------------
@app.route("/employee/<int:id>")
def view_employee(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.*, p.title AS position_name, d.name AS department_name
        FROM Employee e
        LEFT JOIN Position p ON e.position_id = p.position_id
        LEFT JOIN Department d ON e.department_id = d.department_id
        WHERE e.employee_id = ?
    """, id)

    emp = cur.fetchone()

    if not emp:
        conn.close()
        flash("Сотрудник не найден!", "error")
        return redirect(url_for("index"))

    # зарплаты
    cur.execute("""
        SELECT salary_id, amount, from_date, to_date
        FROM Salary
        WHERE employee_id = ?
        ORDER BY from_date DESC
    """, id)
    salaries = cur.fetchall()

    # отпуска
    cur.execute("""
        SELECT vacation_id, start_date, end_date
        FROM Vacation
        WHERE employee_id = ?
        ORDER BY start_date DESC
    """, id)
    vacations = cur.fetchall()

    conn.close()

    return render_template(
        "view_employee.html",
        emp=emp,
        salaries=salaries,
        vacations=vacations
    )

# ----------------------------------------
# Удаление сотрудника
# ----------------------------------------
@app.route("/delete/<int:id>", methods=["POST"])
def delete_employee(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM Salary WHERE employee_id = ?", id)
    cur.execute("DELETE FROM Vacation WHERE employee_id = ?", id)
    cur.execute("DELETE FROM Employee WHERE employee_id = ?", id)

    conn.commit()
    conn.close()

    flash("Сотрудник удалён!", "info")
    return redirect(url_for("index"))

# ----------------------------------------
# Старт приложения
# ----------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
