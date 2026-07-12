#!/usr/bin/env python3
import time
from Foundation import NSObject, NSRunLoop, NSDate
import CoreBluetooth as CB

class PeripheralDelegate(NSObject):
    def peripheralManagerDidUpdateState_(self, manager):
        if manager.state() == CB.CBManagerStatePoweredOn:
            print("Advertising…")
            advertisement = {
                CB.CBAdvertisementDataLocalNameKey: "Hello Domi",
                CB.CBAdvertisementDataServiceUUIDsKey: []  # optional
            }
            manager.startAdvertising_(advertisement)
        else:
            print("Bluetooth state:", manager.state())

def main():
    delegate = PeripheralDelegate.alloc().init()
    peripheral = CB.CBPeripheralManager.alloc().initWithDelegate_queue_options_(
        delegate, None, None
    )

    rl = NSRunLoop.currentRunLoop()
    try:
        while True:
            rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            time.sleep(0.1)
    except KeyboardInterrupt:
        peripheral.stopAdvertising()
        print("Stopped advertising")

if __name__ == "__main__":
    main()
