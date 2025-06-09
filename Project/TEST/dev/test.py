import board
import adafruit_dht
import threading
import time

class DHTReader:
    def __init__(self):
        self.dhtDevice = adafruit_dht.DHT11(board.D21)
        self.temperature = None
        self.humidity = None
        self.running = True
        threading.Thread(target=self._update_values, daemon=True).start()

    def _update_values(self):
        while self.running:
            try:
                self.temperature = self.dhtDevice.temperature
                self.humidity = self.dhtDevice.humidity
                print(f"[Sensor] Temp: {self.temperature}, Humidity: {self.humidity}")
            except Exception as e:
                print("[Sensor Error]:", e)
                self.temperature = None
                self.humidity = None
            time.sleep(5)

    def get_values(self):
        return self.temperature, self.humidity

    def stop(self):
        self.running = False
