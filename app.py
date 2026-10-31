
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "devicedesk_hackathon_secret"

def connect():
    con = sqlite3.connect("devices.db")
    con.row_factory = sqlite3.Row
    return con

def setup():
    con = connect()

    con.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, password TEXT, role TEXT)""")

    con.execute("""CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, device TEXT, issue TEXT,
        status TEXT DEFAULT 'Open')""")

    con.execute("""CREATE TABLE IF NOT EXISTS devices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee TEXT, device TEXT, asset_tag TEXT)""")

    columns = [row["name"] for row in
               con.execute("PRAGMA table_info(tickets)").fetchall()]

    if "priority" not in columns:
        con.execute("ALTER TABLE tickets ADD COLUMN priority TEXT DEFAULT 'Medium'")

    users = [
        ("admin", "admin123", "admin"),
        ("employee", "emp123", "employee")
    ]

    for username, password, role in users:
        user = con.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

        if not user:
            con.execute("INSERT INTO users VALUES(?,?,?)",
                (username, generate_password_hash(password), role))

    con.commit()
    con.close()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        con = connect()
        user = con.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form["username"],)
        ).fetchone()
        con.close()

        if user and check_password_hash(
            user["password"], request.form["password"]
        ):
            session.clear()
            session["user"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin")
            return redirect("/employee")

        return render_template("login.html", error="Invalid login details")

    return render_template("login.html")


@app.route("/employee")
def employee():
    if session.get("role") != "employee":
        return redirect("/")

    con = connect()
    tickets = con.execute(
        "SELECT * FROM tickets WHERE name=? ORDER BY id DESC",
        (session["user"],)
    ).fetchall()

    devices = con.execute(
        "SELECT * FROM devices WHERE employee=?",
        (session["user"],)
    ).fetchall()

    con.close()
    return render_template("index.html", tickets=tickets, devices=devices)


@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/")

    search = request.args.get("search", "")
    status = request.args.get("status", "")

    con = connect()

    query = "SELECT * FROM tickets WHERE name LIKE ?"
    values = ["%" + search + "%"]

    if status:
        query += " AND status=?"
        values.append(status)

    tickets = con.execute(
        query + " ORDER BY id DESC", values
    ).fetchall()

    devices = con.execute(
        "SELECT * FROM devices ORDER BY id DESC"
    ).fetchall()

    all_tickets = con.execute("SELECT status FROM tickets").fetchall()

    stats = {
        "total": len(all_tickets),
        "open": sum(t["status"] == "Open" for t in all_tickets),
        "progress": sum(t["status"] == "In Progress" for t in all_tickets),
        "resolved": sum(t["status"] == "Resolved" for t in all_tickets)
    }

    con.close()

    return render_template(
        "admin.html", tickets=tickets,
        devices=devices, stats=stats,
        search=search, selected_status=status
    )


@app.route("/add", methods=["POST"])
def add():
    if session.get("role") != "employee":
        return redirect("/")

    con = connect()
    con.execute(
        """INSERT INTO tickets(name,device,issue,status,priority)
           VALUES(?,?,?,?,?)""",
        (
            session["user"],
            request.form["device"],
            request.form["issue"],
            "Open",
            request.form["priority"]
        )
    )
    con.commit()
    con.close()
    return redirect("/employee")


@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if session.get("role") != "admin":
        return redirect("/")

    con = connect()
    con.execute(
        "UPDATE tickets SET status=? WHERE id=?",
        (request.form["status"], id)
    )
    con.commit()
    con.close()
    return redirect("/admin")


@app.route("/device", methods=["POST"])
def add_device():
    if session.get("role") != "admin":
        return redirect("/")

    con = connect()
    con.execute(
        "INSERT INTO devices(employee,device,asset_tag) VALUES(?,?,?)",
        (
            request.form["employee"],
            request.form["device"],
            request.form["asset_tag"]
        )
    )
    con.commit()
    con.close()
    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    setup()
    app.run(debug=True)
