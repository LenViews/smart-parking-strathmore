const int sensorPins[] = {A0, A1, A2, A3};
const int numSlots = 4;

const int threshold = 30;

int lastState[4] = {-1, -1, -1, -1};

void setup() {
  Serial.begin(9600);
}

void loop() {
  for (int i = 0; i < numSlots; i++) {
    int value = analogRead(sensorPins[i]);

    // REVERSED LOGIC (IMPORTANT)
    int currentState = (value > threshold) ? 1 : 0;

    if (currentState != lastState[i]) {
      lastState[i] = currentState;

      Serial.print("SLOT_");
      Serial.print(i + 1);
      Serial.print(":");
      Serial.println(currentState ? "OCCUPIED" : "FREE");
    }
  }

  delay(300);
}
