import serial
import requests

SERIAL_PORT = 'COM5'
BAUD_RATE = 9600

ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

mapping = {
    "SLOT_1": 1,
    "SLOT_2": 2,
    "SLOT_3": 3,
    "SLOT_4": 4
}

print("Listening to Arduino...")

while True:
    try:
        line = ser.readline().decode().strip()
        print("Received:", line)

        if ":" in line:
            slot, status = line.split(":")
            slot_id = mapping.get(slot)

            if slot_id:
                requests.post(
                    "http://127.0.0.1:5000/update_slot",
                    json={
                        "slot_id": slot_id,
                        "status": status
                    }
                )

    except Exception as e:
        print("Error:", e)
