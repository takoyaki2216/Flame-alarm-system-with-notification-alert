import network
import urequests
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
VIRTUAL_PIN1 = "V0"  # Address input
VIRTUAL_PIN2 = "V1"  # Fourier energy

# === ntfy Topic ===
NTFY_TOPIC = ""

# === Sensor & Actuator Setup ===
sensor_pin = ADC(Pin(32))
sensor_pin.atten(ADC.ATTN_11DB)
buzzer_pin = Pin(25, Pin.OUT)

# === Globals ===
high_threshold = 3500
fire_alert_active = False
text_input = "Unknown Location"
last_filtered_value = None
sensor_readings = []
MAX_READINGS = 10

# === Wi-Fi Connect ===
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("Connected:", wlan.ifconfig())

# === Laplace smoothing method ===
def apply_laplace_filter(new_value, alpha=0.1):
    global last_filtered_value
    if last_filtered_value is None:
        last_filtered_value = new_value
    last_filtered_value = alpha * new_value + (1 - alpha) * last_filtered_value
    return last_filtered_value

# === Fourier analysis ===
def compute_fourier_energy(data):
    N = len(data)
    energy = 0
    for k in range(1, N // 2):
        real = sum(data[n] * math.cos(2 * math.pi * k * n / N) for n in range(N))
        imag = sum(data[n] * -math.sin(2 * math.pi * k * n / N) for n in range(N))
        energy += math.sqrt(real**2 + imag**2)
    return round(energy / (N // 2), 2)

# === Telegram ===
def send_telegram_message(message):
    base_url = "https://api.telegram.org"
    url = f"{base_url}/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message.replace(' ', '%20')}"
    try:
        response = urequests.get(url)
        print("Telegram response:", response.status_code)
        response.close()
        return True
    except Exception as e:
        print("Telegram failed:", e)
        return False

# === Push notifications ===
def send_ntfy_alert(message):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {'Title': 'Fire Alert!'}
    try:
        response = urequests.post(url, data=message, headers=headers)
        print("ntfy response:", response.status_code)
        response.close()
    except Exception as e:
        print("ntfy failed:", e)

# === Blynk data fetch ===
def fetch_blynk_input(timer=None):
    global text_input
    try:
        url = f"https://blynk.cloud/external/api/get?token={BLYNK_TOKEN}&{VIRTUAL_PIN1}"
        response = urequests.get(url)
        if response.status_code == 200:
            text_input = response.text.strip('"')
        response.close()
    except Exception as e:
        print("Blynk input fetch failed:", e)

# === Blynk chart ===
def send_to_blynk(pin, value):
    try:
        url = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}&{pin}={value}"
        response = urequests.get(url)
        response.close()
    except Exception as e:
        print(f"Blynk V{pin} send failed:", e)

# === Fire status ===
def send_fire_status_to_blynk(status):
    try:
        encoded = status.replace(" ", "%20")
        url = f"https://blynk.cloud/external/api/update?token={BLYNK_TOKEN}&V2={encoded}"
        response = urequests.get(url)
        response.close()
    except Exception as e:
        print("Blynk fire status failed:", e)

# === Blynk event ===
def log_blynk_event(event_code):
    try:
        url = f"https://blynk.cloud/external/api/logEvent?token={BLYNK_TOKEN}&code={event_code}"
        response = urequests.get(url)
        if response.status_code == 200:
            print(f"Blynk event '{event_code}' logged.")
        else:
            print(f"Blynk event failed: {response.status_code}")
        response.close()
    except Exception as e:
        print("Blynk log event failed:", e)

# === Flame Detection Handler ===
def check_flame_status(filtered_value):
    global fire_alert_active
    if filtered_value < high_threshold and not fire_alert_active:
        fire_alert_active = True
        buzzer_pin.value(1)
        send_fire_status_to_blynk('STATUS: FIRE DETECTED')
        alert = f"Fire detected at {text_input}! Please respond immediately!"
        # if telegram is not working or falling into ECONNRESET error
        if not send_telegram_message(alert):
            print("Falling back to Blynk + ntfy.")
            send_ntfy_alert(alert)
            log_blynk_event("fire_detected")
    elif filtered_value > high_threshold and fire_alert_active:
        fire_alert_active = False
        buzzer_pin.value(0)
        send_fire_status_to_blynk('STATUS: NO FIRE DETECTED')
        log_blynk_event("fire_cleared")

# === Main Loop ===
def main():
    connect_wifi()
    fetch_blynk_input()

    timer = Timer(-1)
    timer.init(period=5000, mode=Timer.PERIODIC, callback=fetch_blynk_input)

    while True:
        raw_value = sensor_pin.read()
        filtered_value = apply_laplace_filter(raw_value)

        sensor_readings.append(raw_value)
        if len(sensor_readings) > MAX_READINGS:
            sensor_readings.pop(0)

        if len(sensor_readings) == MAX_READINGS:
            fourier = compute_fourier_energy(sensor_readings)
            send_to_blynk(VIRTUAL_PIN2, fourier)

        print(f"Raw: {raw_value} | Filtered: {round(filtered_value, 2)}")
        check_flame_status(filtered_value)
        time.sleep(1)

main()
