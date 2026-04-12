from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
import MySQLdb
from flask import g
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

def get_db():
    if 'db' not in g:
        g.db = MySQLdb.connect(
            host="localhost",
            user="parking_user",
            passwd="strongpassword",
            db="smart_parking",
            autocommit=False
        )
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ------------------ HELPERS ------------------

def authorize(role, allowed):
    return role in allowed

def cleanup_expired(cursor):
    # Mark expired
    cursor.execute("""
        UPDATE reservations
        SET status='EXPIRED', active=FALSE
        WHERE expiry_time < NOW() AND active=TRUE
    """)

    # Free slots
    cursor.execute("""
        UPDATE parking_slots
        SET status='FREE'
        WHERE id NOT IN (
            SELECT slot_id FROM reservations WHERE active=TRUE
        )
    """)


# ------------------ ROUTES ------------------
# ------------------ SLOTS ------------------

@app.route('/slots')
def get_slots():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT * FROM parking_slots")
    data = cursor.fetchall()

    cursor.close()
    return jsonify(data)

# ------------------ ADD SLOTS -----------------
@app.route('/add_slot', methods=['POST'])
def add_slot():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("INSERT INTO parking_slots (status) VALUES ('FREE')")

    user_id = request.json.get('user_id')

    cursor.execute(
        "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
        (user_id, "Added new parking slot")
    )

    db.commit()

    socketio.emit('slots_updated')
    return jsonify({"message": "Slot added"})

# ------------------ UPDATE SLOT ------------------

@app.route('/update_slot', methods=['POST'])
def update_slot():
    db = get_db()
    cursor = db.cursor()

    data = request.json
    slot_id = data.get('slot_id')
    status = data.get('status')

    if not slot_id or not status:
        return jsonify({"message": "Invalid data"}), 400

    try:
        cursor.execute(
            "UPDATE parking_slots SET status=%s WHERE id=%s",
            (status, slot_id)
        )

        cursor.execute(
            "INSERT INTO sensor_logs (slot_id, status) VALUES (%s, %s)",
            (slot_id, status)
        )

        db.commit()
        socketio.emit('slots_updated')
        return jsonify({"message": "Slot updated"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()

# --------------- DELETE SLOT ---------------
@app.route('/delete_slot', methods=['POST'])
def delete_slot():
    db = get_db()
    cursor = db.cursor()

    slot_id = request.json.get('slot_id')

    cursor.execute("DELETE FROM parking_slots WHERE id=%s", (slot_id,))

    user_id = request.json.get('user_id')

    cursor.execute(
        "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
        (user_id, f"Deleted slot {slot_id}")
    )

    db.commit()

    socketio.emit('slots_updated')
    return jsonify({"message": "Slot removed"})

# --------------- FORCE FREE ALL SLOTS --------------
@app.route('/force_free_all', methods=['POST'])
def force_free_all():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM reservations")
    cursor.execute("UPDATE parking_slots SET status='FREE'")

    user_id = request.json.get('user_id')

    cursor.execute(
        "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
        (user_id, "Emergency reset: all slots freed")
    )

    db.commit()
    socketio.emit('slots_updated')

    return jsonify({"message": "All slots freed"})

# ------------------ ENTRY ------------------

@app.route('/entry', methods=['POST'])
def entry():
    db = get_db()
    cursor = db.cursor()

    data = request.json
    plate = request.json.get('plate')
    user_id = data.get('user_id')

    if user_id:
        cursor.execute("SELECT vehicle_plate FROM users WHERE id=%s", (user_id,))
        row = cursor.fetchone()

        if row and row[0]:
            plate = row[0]

    if not plate:
        return jsonify({"message": "Vehicle Plate Required"}), 400

    try:
        cursor.execute(
            "INSERT INTO entry_logs (vehicle_plate, user_id) VALUES (%s, %s)",
            (plate, user_id)
        )
        db.commit()
        socketio.emit('logs_updated')
        return jsonify({"message": "Entry logged"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()


# ------------------ EXIT ------------------

@app.route('/exit', methods=['POST'])
def exit():
    db = get_db()
    cursor = db.cursor()

    plate = request.json.get('plate')

    try:
        cursor.execute(
            "UPDATE entry_logs SET exit_time=NOW() WHERE vehicle_plate=%s AND exit_time IS NULL",
            (plate,)
        )
        db.commit()
        socketio.emit('logs_updated')
        return jsonify({"message": "Exit logged"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()


# ------------------ REGISTER ------------------

@app.route('/register', methods=['POST'])
def register():
    db = get_db()
    cursor = db.cursor()

    data = request.json

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
        socketio.emit('users_updated')
        return jsonify({"message": "User registered"})

    except MySQLdb.IntegrityError:
        db.rollback()
        return jsonify({"message": "Email exists"}), 400

    except Exception as e:
        print("Register Error:", str(e))
        db.rollback()
        return jsonify({
            "message": "Registration failed",
            "error": str(e)
        }), 500

    finally:
        cursor.close()


# ------------------ LOGIN ------------------

@app.route('/login', methods=['POST'])
def login():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    data = request.json

    cursor.execute("SELECT * FROM users WHERE email=%s", (data['email'],))
    user = cursor.fetchone()

    cursor.close()

    if not user:
        return jsonify({"message": "User not found"}), 404

    if not user.get('active', True):
        return jsonify({"message": "Account is disabled"}), 403

    if not check_password_hash(user['password'], data['password']):
        return jsonify({"message": "Invalid credentials"}), 401

    return jsonify({
        "user": {
        "id": user['id'],
        "name": user['name'],
        "role": user['role']
    }
    })

# ------------------ RESERVE ------------------

@app.route('/reserve', methods=['POST'])
def reserve():
    db = get_db()
    cursor = db.cursor()

    data = request.json
    role = data.get('role')

    if not authorize(role, ['student', 'staff', 'admin']):
        return jsonify({"message": "Unauthorized"}), 403

    slot_id = data.get('slot_id')
    user_id = data.get('user_id')

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

        cursor.execute("SELECT COUNT(*) FROM parking_slots WHERE status='FREE'")
        free_slots = cursor.fetchone()[0]
        if free_slots == 0:
            socketio.emit('system_warning', {
                "message": "Parking is FULL"
            })

        expiry = datetime.now() + timedelta(minutes=10)

        cursor.execute(
            "INSERT INTO reservations (slot_id, user_id, expiry_time, status, active) VALUES (%s,%s,%s, 'ACTIVE', TRUE)",
            (slot_id, user_id, expiry)
        )

        cursor.execute(
            "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
            (user_id, f"Reserved slot {slot_id}")
        )

        db.commit()
        socketio.emit('reservation_created', {
            "slot_id": slot_id,
            "user_id": user_id
        })
        return jsonify({"message": "Reserved successfully"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()

# ------------ ADMIN RESERVATIONS -------------------
@app.route('/admin/reservations')
def admin_reservations():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT r.id, r.slot_id, r.user_id, r.expiry_time, r.status, 
               u.name as user_name, ps.slot_number
        FROM reservations r
        JOIN parking_slots ps ON r.slot_id = ps.id
        LEFT JOIN users u ON r.user_id = u.id
        WHERE r.active = TRUE
        ORDER BY r.expiry_time
    """)
    return jsonify(cursor.fetchall())

# ------------------ RELEASE ------------------

@app.route('/release', methods=['POST'])
def release():
    db = get_db()
    cursor = db.cursor()

    data = request.json
    user_id = data.get('user_id')

    role = data.get('role')

    if not authorize(role, ['admin']):
        return jsonify({"message": "Admin only"}), 403

    slot_id = data.get('slot_id')

    try:
        cursor.execute(
            "DELETE FROM reservations WHERE slot_id=%s",
            (slot_id,)
        )

        cursor.execute(
            "UPDATE parking_slots SET status='FREE' WHERE id=%s",
            (slot_id,)
        )

        cursor.execute(
            "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
            (user_id, f"Admin released slot {slot_id}")
        )

        db.commit()
        socketio.emit('slots_updated')
        socketio.emit('security_alert', {
            "message": "Unauthorized access attempt"
        })
        return jsonify({"message": "Released"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()

# ------------- CANCEL RESERVATION ------------------
@app.route('/cancel_reservation', methods=['POST'])
def cancel_reservation():
    db = get_db()
    cursor = db.cursor()

    data = request.json
    user_id = data.get('user_id')
    slot_id = data.get('slot_id')

    if not user_id or not slot_id:
        return jsonify({"message": "Invalid data"}), 400

    try:
        db.begin()

        # Ensure reservation belongs to this user
        cursor.execute(
            "SELECT id FROM reservations WHERE slot_id=%s AND user_id=%s",
            (slot_id, user_id)
        )
        reservation = cursor.fetchone()

        if not reservation:
            return jsonify({"message": "Reservation not found"}), 404

        # Cancel reservation - Soft cancel instead of deletion
        cursor.execute(
            "UPDATE reservations SET status='CANCELLED', active=FALSE WHERE slot_id=%s AND user_id=%s AND active=TRUE",
            (slot_id, user_id)
        )

        # Free the slot
        cursor.execute(
            "UPDATE parking_slots SET status='FREE' WHERE id=%s",
            (slot_id,)
        )

        cursor.execute(
            "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
            (user_id, f"Cancelled reservation for slot {slot_id}")
        )

        db.commit()

        socketio.emit('reservation_cancelled', {
            "slot_id": slot_id,
            "user_id": user_id
        })
        socketio.emit('slots_updated')
        socketio.emit('logs_updated')

        return jsonify({"message": "Reservation cancelled successfully"})

    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error", "error": str(e)}), 500

    finally:
        cursor.close()

#  ----------------- ANALYTICS -------------------
@app.route('/analytics')
def analytics():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    # occupancy
    cursor.execute("SELECT COUNT(*) as total FROM parking_slots")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as occupied FROM parking_slots WHERE status='OCCUPIED'")
    occupied = cursor.fetchone()['occupied']

    # reservations today
    cursor.execute("""
        SELECT COUNT(*) as today_reservations
        FROM reservations
        WHERE DATE(created_at) = CURDATE()
    """)
    today = cursor.fetchone()['today_reservations']

    return jsonify({
        "occupancy_rate": round((occupied/total)*100, 2) if total else 0,
        "occupied": occupied,
        "total": total,
        "today_reservations": today
    })


# ------------------ USER RESERVATIONS ------------------

@app.route('/my_reservations')
def my_reservations():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    user_id = request.args.get('user_id')

    cursor.execute("SELECT * FROM reservations WHERE user_id=%s", (user_id,))
    data = cursor.fetchall()

    cursor.close()
    return jsonify(data)


# ------------------ LOGS ------------------

@app.route('/logs')
def logs():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    user_id = request.args.get('user_id')

    if user_id:
        cursor.execute(
                "SELECT * FROM entry_logs WHERE user_id=%s ORDER BY entry_time DESC LIMIT 20",
                (user_id,)
        )
    else:
        cursor.execute(
                "SELECT * FROM entry_logs ORDER BY entry_time DESC LIMIT 20"
        )
    data = cursor.fetchall()

    cursor.close()
    return jsonify(data)


# ------------------ USERS ------------------

@app.route('/users')
def users():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT id,name,role,active FROM users")
    data = cursor.fetchall()

    cursor.close()
    return jsonify(data)

# ----------------- SUSPEND USER ---------------
@app.route('/toggle_user', methods=['POST'])
def toggle_user():
    db = get_db()
    cursor = db.cursor()

    data = request.json

    cursor.execute(
        "UPDATE users SET active = NOT active WHERE id=%s",
        (data['user_id'],)
    )

    admin_id = data.get('user_id')          # admin performing action
    target_id = data.get('user_id')        # same here unless you separate

    cursor.execute(
        "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
        (admin_id, f"Toggled active status for user {target_id}")
    )

    db.commit()
    socketio.emit('users_updated')

    return jsonify({"message": "User status updated"})

# ----------------- PROMOTE USER --------------
@app.route('/change_role', methods=['POST'])
def change_role():
    db = get_db()
    cursor = db.cursor()

    data = request.json

    cursor.execute(
        "UPDATE users SET role=%s WHERE id=%s",
        (data['role'], data['user_id'])
    )

    admin_id = data.get('admin_id')
    target_id = data.get('user_id')
    new_role = data.get('role')

    cursor.execute(
        "INSERT INTO audit_logs (user_id, action) VALUES (%s, %s)",
        (admin_id, f"Changed role of user {target_id} to {new_role}")
    )

    db.commit()
    socketio.emit('users_updated')

    return jsonify({"message": "Role updated"})


# --------------- PROFILE -----------------
@app.route('/profile', methods=['GET'])
def get_profile():
    db = get_db()
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    user_id = request.args.get('user_id')
    cursor.execute("SELECT id, name, email, role, vehicle_plate FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"message": "User not found"}), 404
    return jsonify(user)

@app.route('/profile', methods=['PUT'])
def update_profile():
    db = get_db()
    cursor = db.cursor()
    data = request.json
    user_id = data.get('user_id')
    name = data.get('name')
    email = data.get('email')
    vehicle_plate = data.get('vehicle_plate')
    password = data.get('password')  # optional, if provided hash it
    
    try:
        if password:
            hashed = generate_password_hash(password)
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, vehicle_plate=%s, password=%s WHERE id=%s",
                (name, email, vehicle_plate, hashed, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET name=%s, email=%s, vehicle_plate=%s WHERE id=%s",
                (name, email, vehicle_plate, user_id)
            )
        db.commit()
        socketio.emit('users_updated')
        return jsonify({"message": "Profile updated"})
    except MySQLdb.IntegrityError:
        db.rollback()
        return jsonify({"message": "Email already exists"}), 400
    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500


# ------------------ GATE ------------------

@app.route('/open_gate', methods=['POST'])
def open_gate():
    print("Gate Open Triggered")
    return jsonify({"message": "Gate opened"})


if __name__ == '__main__':
    socketio.run(app, debug=True)
