# gatt_tb2_loop_smooth.py
import asyncio
from bleak import BleakClient, BleakScanner

MAC = "FABCEA8B-7EC8-2594-4879-2B3B63989660"
CHAR_COMMAND = "0000fff5-0000-1000-8000-00805f9b34fb"
CHAR_STATUS  = "0000fff3-0000-1000-8000-00805f9b34fb"

CMD_0D = bytearray([0x0D])

PING_INTERVAL = 1.2     # weich, smooth
SOFT_TIMEOUT  = 5.0      # kein crash bei Timeout

last_rx = 0


def handle_notification(sender, data):
    global last_rx
    last_rx = asyncio.get_event_loop().time()

    hex_str = data.hex("-")
    print(f"[NOTIFY] {hex_str}")


async def main():
    global last_rx

    print("Scanning…")
    dev = await BleakScanner.find_device_by_address(MAC, timeout=15)
    if not dev:
        print("Device not found.")
        return

    print(f"Connecting to {dev.address}: {dev.name}")
    async with BleakClient(dev) as client:
        print("Connected ✔")

        # Notifications ON
        await client.start_notify(CHAR_STATUS, handle_notification)

        print("Starting smooth loop… (CTRL+C to exit)")
        last_rx = asyncio.get_event_loop().time()

        while True:
            # 1) Ping senden
            await client.write_gatt_char(CHAR_COMMAND, CMD_0D)
            print("→ Sent 0x0D")

            # 2) Check: Timeout nur loggen, nicht crashen
            now = asyncio.get_event_loop().time()
            if now - last_rx > SOFT_TIMEOUT:
                print("⚠️  No data for a while… (soft warning)")

            # 3) Soft delay – blockiert nicht
            await asyncio.sleep(PING_INTERVAL)

        # wird nie erreicht
        await client.stop_notify(CHAR_STATUS)


if __name__ == "__main__":
    asyncio.run(main())
