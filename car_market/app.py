from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
import sqlite3
from pathlib import Path
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
DB_PATH = Path("database.db")

# ---- configurare upload + sesiune ----
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = "super_secret_key_123"


# ---- afișare fișiere upload ----
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---- conexiune DB ----
def get_conn():
    return sqlite3.connect(DB_PATH)


# ---- creare tabele (users, brands, cars) ----
def init_db():
    with get_conn() as conn:
        # utilizatori
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        # mărci
        conn.execute("""
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # mașini
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER,
                price REAL,
                description TEXT,
                image TEXT,
                user_id INTEGER,
                phone TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # dacă nu avem nici o marcă, băgăm un set default
        count = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        if count == 0:
            default_brands = [
                "Audi", "BMW", "Mercedes", "Volkswagen", "Skoda", "Seat",
                "Ford", "Opel", "Renault", "Peugeot", "Toyota", "Hyundai"
            ]
            for name in default_brands:
                conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (name,))

        conn.commit()


# ---- helper: listă mărci ----
def get_brands():
    with get_conn() as conn:
        rows = conn.execute("SELECT name FROM brands ORDER BY name ASC").fetchall()
    return [r[0] for r in rows]


# ---- pagina principală + căutare ----
@app.route("/", methods=["GET", "POST"])
def index():
    search = request.form.get("search", "").strip()

    with get_conn() as conn:
        if search:
            query = f"%{search}%"
            cars = conn.execute(
                """SELECT c.id, c.brand, c.model, c.year, c.price, c.description,
                          c.image, u.username, c.phone, c.user_id
                   FROM cars c
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE c.brand LIKE ? OR c.model LIKE ?
                   ORDER BY c.id DESC""",
                (query, query)
            ).fetchall()
        else:
            cars = conn.execute(
                """SELECT c.id, c.brand, c.model, c.year, c.price, c.description,
                          c.image, u.username, c.phone, c.user_id
                   FROM cars c
                   LEFT JOIN users u ON c.user_id = u.id
                   ORDER BY c.id DESC"""
            ).fetchall()

    return render_template("index.html", cars=cars, search=search)


# ---- înregistrare user ----
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Completează toate câmpurile.")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)

        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed_pw)
                )
                conn.commit()
            flash("Cont creat cu succes! Te poți loga acum.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Numele de utilizator există deja.")

    return render_template("register.html")


# ---- login user ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_conn() as conn:
            user = conn.execute(
                "SELECT id, password FROM users WHERE username=?",
                (username,)
            ).fetchone()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            flash("Autentificare reușită!")
            return redirect(url_for("index"))
        else:
            flash("Date incorecte.")

    return render_template("login.html")


# ---- logout ----
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("Te-ai delogat cu succes.")
    return redirect(url_for("index"))


# ---- adăugare mașină ----
@app.route("/add", methods=["GET", "POST"])
def add_car():
    if "user_id" not in session:
        flash("Trebuie să fii logat pentru a adăuga un anunț.")
        return redirect(url_for("login"))

    if request.method == "POST":
        brand_choice = request.form.get("brand")
        brand_new = request.form.get("brand_new", "").strip()
        model = request.form["model"]
        year = request.form["year"]
        price = request.form["price"]
        description = request.form["description"]
        phone = request.form["phone"]

        # alegem marca finală
        if brand_choice == "_other":
            if not brand_new:
                flash("Ai ales 'Altă marcă...', dar nu ai introdus marca nouă.")
                return redirect(url_for("add_car"))
            brand_final = brand_new
        else:
            brand_final = brand_choice

        # imagine
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(file_save_path)
            image_path = f"uploads/{filename}"

        with get_conn() as conn:
            # dacă e marcă nouă -> o băgăm în brands
            if brand_choice == "_other":
                conn.execute(
                    "INSERT OR IGNORE INTO brands (name) VALUES (?)",
                    (brand_final,)
                )

            conn.execute(
                """INSERT INTO cars (brand, model, year, price, description, image, user_id, phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (brand_final, model, year, price, description, image_path, session["user_id"], phone)
            )
            conn.commit()

        flash("Anunț adăugat cu succes!")
        return redirect(url_for("index"))

    brands = get_brands()
    return render_template("add_car.html", brands=brands)


# ---- editare mașină ----
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_car(id):
    if "user_id" not in session:
        flash("Trebuie să fii logat pentru a edita anunțuri.")
        return redirect(url_for("login"))

    with get_conn() as conn:
        car = conn.execute("SELECT * FROM cars WHERE id=?", (id,)).fetchone()

    if not car:
        return "Anunțul nu există."

    # car[7] = user_id
    if car[7] != session["user_id"]:
        return "Nu poți edita un anunț care nu îți aparține."

    if request.method == "POST":
        brand_choice = request.form.get("brand")
        brand_new = request.form.get("brand_new", "").strip()
        model = request.form["model"]
        year = request.form["year"]
        price = request.form["price"]
        description = request.form["description"]
        phone = request.form["phone"]

        # marcă finală
        if brand_choice == "_other":
            if not brand_new:
                flash("Ai ales 'Altă marcă...', dar nu ai introdus marca nouă.")
                return redirect(url_for("edit_car", id=id))
            brand_final = brand_new
        else:
            brand_final = brand_choice

        # imagine (dacă nu selectăm nimic nou, păstrăm vechea cale)
        image_file = request.files.get("image")
        image_path = car[6]
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(file_save_path)
            image_path = f"uploads/{filename}"

        with get_conn() as conn:
            if brand_choice == "_other":
                conn.execute(
                    "INSERT OR IGNORE INTO brands (name) VALUES (?)",
                    (brand_final,)
                )

            conn.execute(
                """UPDATE cars
                   SET brand=?, model=?, year=?, price=?, description=?, image=?, phone=?
                   WHERE id=?""",
                (brand_final, model, year, price, description, image_path, phone, id)
            )
            conn.commit()

        flash("Anunț actualizat cu succes!")
        return redirect(url_for("index"))

    # GET: încărcăm mărci + avem grijă ca marca actuală să fie în listă
    brands = get_brands()
    if car[1] not in brands:
        brands.append(car[1])
        brands.sort()

    return render_template("edit_car.html", car=car, brands=brands)


# ---- ștergere mașină ----
@app.route("/delete/<int:id>", methods=["POST"])
def delete_car(id):
    if "user_id" not in session:
        flash("Trebuie să fii logat pentru a șterge anunțuri.")
        return redirect(url_for("login"))

    with get_conn() as conn:
        car = conn.execute("SELECT * FROM cars WHERE id=?", (id,)).fetchone()

        if not car:
            return "Anunțul nu există."

        if car[7] != session["user_id"]:
            return "Nu poți șterge un anunț care nu îți aparține."

        conn.execute("DELETE FROM cars WHERE id=?", (id,))
        conn.commit()

    flash("Anunț șters cu succes.")
    return redirect(url_for("index"))


# ---- gestionare mărci (listă / admin) ----
@app.route("/admin/brands")
def manage_brands():
    with get_conn() as conn:
        brands = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    return render_template("brands.html", brands=brands)


@app.route("/admin/brands/add", methods=["POST"])
def brand_add():
    name = request.form.get("brand", "").strip()
    if name:
        try:
            with get_conn() as conn:
                conn.execute("INSERT INTO brands (name) VALUES (?)", (name,))
                conn.commit()
            flash("Marcă adăugată.")
        except sqlite3.IntegrityError:
            flash("Marca există deja.")
    return redirect(url_for("manage_brands"))


@app.route("/admin/brands/delete/<int:id>", methods=["POST"])
def brand_delete(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM brands WHERE id=?", (id,))
        conn.commit()
    flash("Marcă ștearsă.")
    return redirect(url_for("manage_brands"))


# ---- main ----
if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)
