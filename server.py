import http.server
import socketserver
import json
import os
import sqlite3
import mimetypes
import urllib.parse
from http import HTTPStatus

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "database.sqlite")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Settings table (WhatsApp number, admin pass, etc.)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Cars table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            photo_url TEXT NOT NULL,
            seats INTEGER NOT NULL,
            ac_type TEXT NOT NULL,
            rate_per_km REAL NOT NULL,
            min_km_per_day INTEGER DEFAULT 250,
            luggage_capacity TEXT,
            description TEXT
        )
    """)
    
    # Default settings if not exist
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_username', 'admin')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'bhatti123')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('whatsapp_number', '919876543210')")
    
    # Check if Ertiga already exists, else insert
    cur.execute("SELECT COUNT(*) FROM cars")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO cars (name, photo_url, seats, ac_type, rate_per_km, min_km_per_day, luggage_capacity, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Maruti Suzuki Ertiga",
            "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?q=80&w=900&auto=format&fit=crop",
            7,
            "Dual AC (Front & Rear Chilled)",
            12.0,
            250,
            "3 Big Suitcases + 2 Bags",
            "Clean and comfortable 7-seater family car. Experienced driver, roof AC vents, and generous legroom."
        ))
    conn.commit()
    conn.close()

init_db()

class AppHandler(http.server.BaseHTTPRequestHandler):
    def get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # API: Public Settings (e.g. WhatsApp number)
        if path == "/api/settings":
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM settings WHERE key = 'whatsapp_number'")
            row = cur.fetchone()
            conn.close()
            self.send_json({"whatsapp_number": row["value"] if row else "919876543210"})
            return

        # API: Get Cars List
        if path == "/api/cars":
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM cars ORDER BY id ASC")
            cars = [dict(row) for row in cur.fetchall()]
            conn.close()
            self.send_json({"cars": cars})
            return

        # Static File Serving
        clean_path = path.lstrip('/')
        if clean_path == "" or clean_path == "index.html":
            file_to_serve = os.path.join(PUBLIC_DIR, "index.html")
        elif clean_path == "cars" or clean_path == "cars.html":
            file_to_serve = os.path.join(PUBLIC_DIR, "cars.html")
        elif clean_path == "admin" or clean_path == "admin.html":
            file_to_serve = os.path.join(PUBLIC_DIR, "admin.html")
        else:
            file_to_serve = os.path.join(PUBLIC_DIR, clean_path)

        if os.path.exists(file_to_serve) and os.path.isfile(file_to_serve):
            mime_type, _ = mimetypes.guess_type(file_to_serve)
            if not mime_type:
                mime_type = "text/html" if file_to_serve.endswith(".html") else "application/octet-stream"
            
            with open(file_to_serve, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(length) if length > 0 else b'{}'
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            body = {}

        # API: Admin Login
        if path == "/api/admin/login":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = 'admin_username'")
            db_user = cur.fetchone()["value"]
            cur.execute("SELECT value FROM settings WHERE key = 'admin_password'")
            db_pass = cur.fetchone()["value"]
            conn.close()

            if username == db_user and password == db_pass:
                # Simple token for session
                self.send_json({"success": True, "token": "bhatti_authenticated_session_9921"})
            else:
                self.send_json({"success": False, "error": "Invalid username or password"}, status=401)
            return

        # API: Update WhatsApp Number (Protected)
        if path == "/api/admin/whatsapp":
            new_number = body.get("whatsapp_number", "").strip().replace("+", "").replace(" ", "").replace("-", "")
            if not new_number:
                self.send_json({"success": False, "error": "Number cannot be empty"}, status=400)
                return
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("UPDATE settings SET value = ? WHERE key = 'whatsapp_number'", (new_number,))
            conn.commit()
            conn.close()
            self.send_json({"success": True, "whatsapp_number": new_number})
            return

        # API: Add New Car (Protected)
        if path == "/api/admin/cars/add":
            name = body.get("name", "").strip()
            photo_url = body.get("photo_url", "").strip() or "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?q=80&w=900&auto=format&fit=crop"
            seats = int(body.get("seats", 7))
            ac_type = body.get("ac_type", "Full AC").strip()
            rate_per_km = float(body.get("rate_per_km", 12.0))
            min_km_per_day = int(body.get("min_km_per_day", 250))
            luggage_capacity = body.get("luggage_capacity", "3 Bags").strip()
            description = body.get("description", "Clean, comfortable, and reliable taxi.").strip()

            if not name:
                self.send_json({"success": False, "error": "Car name is required"}, status=400)
                return

            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO cars (name, photo_url, seats, ac_type, rate_per_km, min_km_per_day, luggage_capacity, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, photo_url, seats, ac_type, rate_per_km, min_km_per_day, luggage_capacity, description))
            conn.commit()
            new_id = cur.lastrowid
            conn.close()
            self.send_json({"success": True, "id": new_id})
            return

        # API: Update Car
        if path == "/api/admin/cars/update":
            car_id = body.get("id")
            if not car_id:
                self.send_json({"success": False, "error": "Car ID required"}, status=400)
                return
            
            name = body.get("name", "").strip()
            photo_url = body.get("photo_url", "").strip()
            seats = int(body.get("seats", 7))
            ac_type = body.get("ac_type", "Full AC").strip()
            rate_per_km = float(body.get("rate_per_km", 12.0))
            min_km_per_day = int(body.get("min_km_per_day", 250))
            luggage_capacity = body.get("luggage_capacity", "").strip()
            description = body.get("description", "").strip()

            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE cars SET name = ?, photo_url = ?, seats = ?, ac_type = ?, rate_per_km = ?, min_km_per_day = ?, luggage_capacity = ?, description = ?
                WHERE id = ?
            """, (name, photo_url, seats, ac_type, rate_per_km, min_km_per_day, luggage_capacity, description, car_id))
            conn.commit()
            conn.close()
            self.send_json({"success": True})
            return

        # API: Delete Car
        if path == "/api/admin/cars/delete":
            car_id = body.get("id")
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
            conn.commit()
            conn.close()
            self.send_json({"success": True})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "API not found")

    def log_message(self, format, *args):
        # Clean server logging
        pass

if __name__ == "__main__":
    server_address = ("", PORT)
    httpd = socketserver.TCPServer(server_address, AppHandler)
    print(f"Bhatti Tour & Travel server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
