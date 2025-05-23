import network
import urequests
import ujson
import time
import math
from machine import Pin, ADC, Timer

# === Wi-Fi Credentials ===
SSID = ''
PASSWORD = ''

# === Telegram Bot Info ===
BOT_TOKEN = ''
CHAT_ID = ''

# === Blynk Info ===
BLYNK_TOKEN = ""
VIRTUAL_PIN1 = "V0" #address
VIRTUAL_PIN2 = "V1" #fourier

# === Sensor and Actuator Setup ===
sensor_pin = ADC(Pin(32))
sensor_pin.atten(ADC.ATTN_11DB)  # Max range (0-4095)
buzzer_pin = Pin(25, Pin.OUT)

# === Thresholds ===
high_threshold = 3500
low_threshold = 4095
fire_alert_active = False
text_input = "Unknown Location"

# === Laplace Filter State ===
last_filtered_value = None

# === Sensor Readings Buffer for Fourier ===
sensor_readings = []
MAX_READINGS = 10  # You can adjust this for resolution vs performance

# === Connect to Wi-Fi ===
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print('Network connected:', wlan.ifconfig())
    
def apply_laplace_filter(new_value, alpha=0.1):
    global last_filtered_value
    if last_filtered_value is None:
        last_filtered_value = new_value
    last_filtered_value = alpha * new_value + (1 - alpha) * last_filtered_value
    return last_filtered_value

def compute_fourier_energy(data):
    N = len(data)
    energy = 0
    for k in range(1, N//2):  # basic DFT-style approximation
        real = sum(data[n] * math.cos(2 * math.pi * k * n / N) for n in range(N))
        imag = sum(data[n] * -math.sin(2 * math.pi * k * n / N) for n in range(N))
        energy += math.sqrt(real**2 + imag**2)
    return round(energy / (N//2), 2)

# === Send Telegram Alert ===
def send_telegram_message(message):
    base_url = "https://api.telegram.org"
    url = f"{base_url}/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message.replace(' ', '%20')}"
    try:
        response = urequests.get(url)
        print("Telegram response:", response.text)
        response.close()
    except Exception as e:
        print("Error sending Telegram message:", e)

# === Fetch Blynk Text Input ===
def fetch_blynk_input(timer=None):
    global text_input
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN1}"
        response = urequests.get(url)
        if response.status_code == 200:
            text_input = response.text.strip('"')
        response.close()
    except Exception as e:
        print("Error fetching Blynk input:", e)

# === Graph fourier analysis to blynk ===
def send_to_blynk(VIRTUAL_PIN2, value):
    try:
        url = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}&{VIRTUAL_PIN2}={value}"
        response = urequests.get(url)
        response.close()
    except Exception as e:
        print(f"Error sending to Blynk V{VIRTUAL_PIN2}:", e)
     
# ==== labeled status ===
def send_fire_status_to_blynk(status):
    try:
        encoded_status = status.replace(" ", "%20")
        url = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}&V2={encoded_status}"
        response = urequests.get(url)
        print("Blynk response status:", response.status_code)
        response.close()
    except Exception as e:
        print("Error sending fire status to Blynk:", e)

# === Flame Detection and Buzzer/Alert Handling ===
def check_flame_status(filtered_value):
    global buzzer_on, fire_alert_active
    if filtered_value < high_threshold and not fire_alert_active:
        # Fire just detected
        fire_alert_active = True
        buzzer_pin.value(1)  # Turn ON buzzer (active LOW)
        send_fire_status_to_blynk('STATUS: FIRE DETECTED')
        
        if text_input != "Unknown Location":
            message = f"Fire Detected at {text_input}! Please respond immediately!"
            send_telegram_message(message)
        else:
            print("Blynk input not ready   skipping Telegram alert.")

    elif filtered_value > high_threshold and fire_alert_active:
        # Fire is gone, reset system
        fire_alert_active = False
        buzzer_pin.value(0)  # Turn OFF buzzer (active LOW)
        print("Fire alert cleared.")
        send_fire_status_to_blynk('STATUS: NO FIRE DETECTED')

# === Main Program ===
def main():
    connect_wifi()
    fetch_blynk_input()

    # Set up periodic Blynk input fetch
    timer = Timer(-1)
    timer.init(period=5000, mode=Timer.PERIODIC, callback=fetch_blynk_input)

    while True:
        raw_value = sensor_pin.read()
        filtered_value = apply_laplace_filter(raw_value)

        # Update the readings buffer
        sensor_readings.append(raw_value)
        if len(sensor_readings) > MAX_READINGS:
            sensor_readings.pop(0)

        # Compute Fourier only when we have enough data
        if len(sensor_readings) == MAX_READINGS:
            fourier_value = compute_fourier_energy(sensor_readings)
            send_to_blynk("V1", fourier_value)

        print(f"Raw: {raw_value} | Filtered (Laplace): {round(filtered_value, 2)}")
        check_flame_status(filtered_value)

        time.sleep(1)

main()
