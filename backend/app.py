from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, jsonify, request
from flask_cors import CORS
import MySQLdb

app = Flask(__name__)
CORS(app)

db = MySQLdb.connect(
    host="localhost",
    user="parking_user",
    passwd="strongpassword",
    db="smart_parking",
    autocommit=False
)

# ------------------ HELPERS ------------------

def authorize(role, allowed):
    return role in allowed

def cleanup_expired(cursor):
    cursor.execute("""
        DELETE FROM reservations 
        WHERE created_at < NOW() - INTERVAL 10 MINUTE
    """)

    cursor.execute("""
        UPDATE parking_slots 
        SET status='FREE'
        WHERE id NOT IN (SELECT slot_id FROM reservations)
    """)

# ------------------ ROUTES ------------------

@app.route('/slots')
def get_slots():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM parking_slots")
    return jsonify(cursor.fetchall())

@app.route('/update_slot', methods=['POST'])
def update_slot():
    data = request.json
    slot_id = data.get('slot_id')
    status = data.get('status')

    if not slot_id or not status:
        return jsonify({"message": "Invalid data"}), 400

    cursor = db.cursor()

    cursor.execute(
        "UPDATE parking_slots SET status=%s WHERE id=%s",
        (status, slot_id)
    )

    cursor.execute(
        "INSERT INTO sensor_logs (slot_id, status) VALUES (%s, %s)",
        (slot_id, status)
    )

    db.commit()
    return jsonify({"message": "Slot updated"})

@app.route('/entry', methods=['POST'])
def entry():
    plate = request.json.get('plate')

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO entry_logs (vehicle_plate) VALUES (%s)",
        (plate,)
    )
    db.commit()

    return jsonify({"message": "Entry logged"})

@app.route('/exit', methods=['POST'])
def exit():
    plate = request.json.get('plate')

    cursor = db.cursor()
    cursor.execute(
        "UPDATE entry_logs SET exit_time=NOW() WHERE vehicle_plate=%s AND exit_time IS NULL",
        (plate,)
    )
    db.commit()

    return jsonify({"message": "Exit logged"})

@app.route('/register', methods=['POST'])
def register():
    data = request.json

    cursor = db.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s)",
            (
                data['name'],
                data['email'],
                generate_password_hash(data['password']),
                data['role']
            )
        )
        db.commit()
        return jsonify({"message": "User registered"})
    except MySQLdb.IntegrityError as e:
        db.rollback()
        return jsonify({"message": "Email exists"}), 400

    except Exception as e:
        db.rollback()
        return jsonify({
            "message": "Registration failed",
            "error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json

    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email=%s", (data['email'],))
    user = cursor.fetchone()

    if user and check_password_hash(user['password'], data['password']):
        return jsonify({
            "user": {
                "id": user['id'],
                "name": user['name'],
                "role": user['role']
            }
        })

    return jsonify({"message": "Invalid credentials"}), 401

# ------------------ RESERVE ------------------

@app.route('/reserve', methods=['POST'])
def reserve():
    data = request.json
    role = data.get('role')

    if not authorize(role, ['student', 'staff', 'admin']):
        return jsonify({"message": "Unauthorized"}), 403

    slot_id = data.get('slot_id')
    user_id = data.get('user_id')

    cursor = db.cursor()

    try:
        db.begin()

        cleanup_expired(cursor)

        cursor.execute(
            "SELECT status FROM parking_slots WHERE id=%s FOR UPDATE",
            (slot_id,)
        )
        row = cursor.fetchone()

        if not row:
            return jsonify({"message": "Slot not found"}), 404

        if row[0] != 'FREE':
            return jsonify({"message": "Slot not available"}), 400

        cursor.execute(
            "UPDATE parking_slots SET status='RESERVED' WHERE id=%s",
            (slot_id,)
        )

        cursor.execute(
            "INSERT INTO reservations (slot_id, user_id) VALUES (%s,%s)",
            (slot_id, user_id)
        )

        db.commit()
        return jsonify({"message": "Reserved successfully"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

# ------------------ RELEASE ------------------

@app.route('/release', methods=['POST'])
def release():
    data = request.json
    role = data.get('role')

    if not authorize(role, ['admin']):
        return jsonify({"message": "Admin only"}), 403

    slot_id = data.get('slot_id')

    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM reservations WHERE slot_id=%s",
        (slot_id,)
    )

    cursor.execute(
        "UPDATE parking_slots SET status='FREE' WHERE id=%s",
        (slot_id,)
    )

    db.commit()

    return jsonify({"message": "Released"})
    
# -------------------- USER RESERVATIONS ---------------

@app.route('/my_reservations')
def my_reservations():
    user_id = request.args.get('user_id')
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM reservations WHERE user_id=%s", (user_id,))
    return jsonify(cursor.fetchall())

# -------------------- LOGS --------------------

@app.route('/logs')
def logs():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM entry_logs ORDER BY entry_time DESC LIMIT 20")
    return jsonify(cursor.fetchall())


# -------------------- USERS ---------------------
# GET users (admin only ideally)

@app.route('/users')
def users():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id,name,role FROM users")
    return jsonify(cursor.fetchall())


# --------------------- GATE ----------------------
# OPEN GATE (simulate servo trigger)

@app.route('/open_gate', methods=['POST'])
def open_gate():
    print("Gate Open Triggered")
    return jsonify({"message":"Gate opened"})



if __name__ == '__main__':
    app.run(debug=True)
