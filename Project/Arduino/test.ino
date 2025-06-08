int soil = A1;
int water = A2;

void setup() {
	Serial.begin(9600);
}

void loop() {
	int soil_R = analogRead(soil);
	int water_R = analogRead(water);
	
	float soil_val += (1023 - soil_R) * 100.0 / 1023;
	float water_val += water_R * 100.0 / 1023;

	Serial.print(soil_val);
	Serial.print(",");
	Serial.println(water_val);

	delay(10000);
}
