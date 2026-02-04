import smbus2

for bus_id in [1, 20, 21]:
    print(f"\nScanning Bus {bus_id}...")
    try:
        bus = smbus2.SMBus(bus_id)
        for addr in range(0x03, 0x78):
            try:
                bus.write_quick(addr)
                print(f"  FOUND device at: 0x{addr:02x}")
            except:
                pass
    except:
        print(f"  Bus {bus_id} not available.")