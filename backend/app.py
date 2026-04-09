from flask import Flask, jsonify, request
from flask_cors import CORS
import MySQLdb

app = Flask(__name__)

CORS(app)

db = MySQLdb.connect(
    host="localhost",
    user="parking_user",
    passwd="strongpassword",
    db="smart_parking"
)

# GET ALL SLOTS
@app.route('/slots', methods=['GET'])
def get_slots():
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM parking_slots")
    return jsonify(cursor.fetchall())

# UPDATE SLOT STATUS
@app.route('/update_slot', methods=['POST'])
def update_slot():
    data = request.json
    slot_id = data['slot_id']
    status = data['status']

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

# ENTRY LOG
@app.route('/entry', methods=['POST'])
def entry():
    plate = request.json['plate']

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO entry_logs (vehicle_plate) VALUES (%s)",
        (plate,)
    )
    db.commit()

    return jsonify({"message": "Entry logged"})

# EXIT LOG
@app.route('/exit', methods=['POST'])
def exit():
    plate = request.json['plate']

    cursor = db.cursor()
    cursor.execute(
        "UPDATE entry_logs SET exit_time=NOW() WHERE vehicle_plate=%s AND exit_time IS NULL",
        (plate,)
    )
    db.commit()

    return jsonify({"message": "Exit logged"})

if __name__ == '__main__':
    app.run(debug=True)
