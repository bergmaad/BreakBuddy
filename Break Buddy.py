import board, busio, displayio, terminalio, time, socketpool, wifi, adafruit_ntp, os, pwmio, math, digitalio
from fourwire import FourWire
from adafruit_st7735r import ST7735R
from adafruit_display_text import label
import rtc, circuitpython_schedule as schedule

# --- WiFi & Time Setup ---
print("Connecting to Wi-Fi...")
wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
print("Connected to Wi-Fi!")
pool = socketpool.SocketPool(wifi.radio)
ntp = adafruit_ntp.NTP(pool, server="pool.ntp.org")
print("Fetching time from NTP...")
# Adjust for timezone (e.g. -4 for EDT)
offset_hours = -4 # Manual offset: change to -4 during DST, -5 otherwise; change when needed
adjusted_time = time.localtime(time.mktime(ntp.datetime) + offset_hours * 3600)
rtc.RTC().datetime = adjusted_time
print("Time set:", adjusted_time)

# --- Button Setup ---
button = digitalio.DigitalInOut(board.GP0)
button.switch_to_input(pull=digitalio.Pull.UP)

# --- Sound Setup ---
audio = pwmio.PWMOut(board.GP16, duty_cycle=0, frequency=440, variable_frequency=True)
def play_note(freq, duration=0.5, vibrato_rate=6, vibrato_depth=4):
    start = time.monotonic()
    while time.monotonic() - start < duration:
        # Apply vibrato modulation
        vibrato = math.sin(2 * math.pi * vibrato_rate * (time.monotonic() - start)) * vibrato_depth
        audio.frequency = int(freq + vibrato)
        audio.duty_cycle = 2**15  # 50% duty
        time.sleep(0.01)
    audio.duty_cycle = 0
def play_intro_chime():
    play_note(261.63, 0.6)  # C4 (Middle C)
    play_note(329.63, 0.6)  # E4 (Major third)
    play_note(392.00, 0.6)  # G4 (Perfect fifth)
def play_exit_chime():
    play_note(392.00, 0.6)  # G4
    play_note(329.63, 0.6)  # E4
    play_note(261.63, 0.6)  # C4

# --- Display Setup ---
displayio.release_displays()
spi = busio.SPI(clock=board.GP14, MOSI=board.GP15)
tft_cs = board.GP5
tft_dc = board.GP6
reset_pin = board.GP7
display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=reset_pin)
display = ST7735R(display_bus, width=128, height=128, colstart=2, rowstart=1)

main_group = displayio.Group()
display.root_group = main_group

# --- Setup Default Display & Shared Parameters  ---
bg_bitmap = displayio.Bitmap(128, 128, 1)
bg_palette = displayio.Palette(1)
bg_tile = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
bg_palette[0] = 0x102840  # Initial color

text_area = label.Label(terminalio.FONT, text="just keep swimming", color=0xFFFFFF)
text_area.x = (128 - text_area.bounding_box[2]) // 2
text_area.y = (128 - text_area.bounding_box[3]) // 2

main_group.append(bg_tile)
main_group.append(text_area)

def fade_background(tile, palette, start_color, end_color, steps=20, delay=0.05): # Function that fades the background /
    # colors from A > B >A
    fade_seq = list(range(steps)) + list(reversed(range(steps)))
    for i in fade_seq:
        factor = i / (steps - 1)
        sr, sg, sb = (start_color >> 16) & 0xFF, (start_color >> 8) & 0xFF, start_color & 0xFF
        er, eg, eb = (end_color >> 16) & 0xFF, (end_color >> 8) & 0xFF, end_color & 0xFF
        r = int(sr + (er - sr) * factor)
        g = int(sg + (eg - sg) * factor)
        b = int(sb + (eb - sb) * factor)
        palette[0] = (r << 16) | (g << 8) | b
        time.sleep(delay)

# --- Breathing Animation ---
def run_breathing_animation():
    play_intro_chime() # Play intro chime

    # Clear and prepare background
    main_group.pop()  # remove text_area
    bg_palette[0] = 0x102840  # reset background

    # Text displayed
    breathe_text = label.Label(terminalio.FONT, text="Take a moment\nto breathe", color=0xFFFFFF)
    breathe_text.x = (128 - breathe_text.bounding_box[2]) // 2
    breathe_text.y = (128 - breathe_text.bounding_box[3]) // 2
    main_group.append(breathe_text)

    def make_square(size, color): # function that draws a square
        bmp = displayio.Bitmap(size, size, 1)
        pal = displayio.Palette(1)
        pal[0] = color
        return displayio.TileGrid(bmp, pixel_shader=pal, x=(128 - size) // 2, y=(128 - size) // 2)

    def interpolate_color(start, end, factor): # function that transitions between 2 colors, given as hexadecimals
        sr, sg, sb = (start >> 16) & 0xFF, (start >> 8) & 0xFF, start & 0xFF
        er, eg, eb = (end >> 16) & 0xFF, (end >> 8) & 0xFF, end & 0xFF
        r = int(sr + (er - sr) * factor)
        g = int(sg + (eg - sg) * factor)
        b = int(sb + (eb - sb) * factor)
        return (r << 16) | (g << 8) | b

    # Inhale/exhale parameters
    square_layer = None
    sizes = list(range(20, 101, 4))
    step_count = len(sizes)
    cycles = 6
    time_per_cycle = 60 / cycles
    inhale_exhale_time = time_per_cycle / 2
    time_per_step = inhale_exhale_time / step_count
    color_a = 0x9575CD  # Lavender
    color_b = 0x102840  # Midnight blue

    for _ in range(cycles): # outer for-loop repeats the inhale-exhale sequences a specified number of times (cycles)
        for i, size in enumerate(sizes): # inner for-loop sets the inhale sequence
            factor = i / (step_count - 1)
            color = interpolate_color(color_a, color_b, factor)
            square = make_square(size, color)
            if square_layer:
                main_group.remove(square_layer)
            square_layer = square
            main_group.insert(-1, square_layer)
            time.sleep(time_per_step)
        time.sleep(0.2)
        for i, size in enumerate(reversed(sizes)): # inner for-loop sets the exhale sequence
            factor = i / (step_count - 1)
            color = interpolate_color(color_b, color_a, factor)
            square = make_square(size, color)
            if square_layer:
                main_group.remove(square_layer)
            square_layer = square
            main_group.insert(-1, square_layer)
            time.sleep(time_per_step)
        time.sleep(0.2)

    # Restore default screen after completing all the inhale-exhale cycles
    main_group.pop()  # remove breathing text
    if square_layer:
        main_group.remove(square_layer)
    play_exit_chime()
    main_group.append(text_area)  # re-add default text

# --- Schedule breathing animation every 45 minutes during the workday ---
def maybe_run_breathing_animation():
    now = time.localtime()
    if 9 <= now.tm_hour < 17:  # Between 9am and 5pm
        run_breathing_animation()

schedule.every(45).minutes.do(maybe_run_breathing_animation)

# --- Main Loop ---
while True:
    schedule.run_pending()

    if not button.value:  # button pressed
        run_breathing_animation()
        time.sleep(1)  # debounce

    fade_background(bg_tile, bg_palette, 0x102840, 0x9575CD)  # default background
