int soil = A1;
int water = A2;

void setup() {
	Serial.begin(9600)
}

void loop() {
	float soil_val = 0;
	float water_val = 0;

	for(int i=0; i<6; i++){
		int soil_R = analogRead(soil);
		int water_R = analogRead(water);
	
		soil_val += (1023 - soil_R) * 100.0 / 1023;
		water_val += water_R * 100.0 / 1023;
		delay(10000);
	}
	soil_val /= 6;
	water_val /= 6;

	Serial.print(soil_val);
	Serial.print(",");
	Serial.println(water_val);
}
