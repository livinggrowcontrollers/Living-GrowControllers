package org.hackintosh1980.blebridge;

import android.bluetooth.*;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.Iterator;
import java.util.Locale;
import java.util.UUID;

public final class LogBridge {

    private static final String TAG = "LogBridge";

    // ---- runtime ----
    private static boolean running = false;
    private static Context app;
    private static BluetoothGatt gatt;
    private static BluetoothDevice device;

    // ---- profile driven ----
    private static String targetMac;
    private static UUID serviceUuid;
    private static UUID notifyUuid;
    private static UUID commandUuid; // <--- NEU
    private static boolean pollMode = false;
    private static long pollIntervalMs = 1500;
    private static byte[][] commandSeq;

    // ---- state ----
    private static BluetoothGattCharacteristic notifyChar;
    private static int commandIndex = 0;

    private static BluetoothGattCharacteristic commandChar;

    // ---- logging ----
    private static JSONArray log = new JSONArray();
    private static File outFile;

    private static final Handler main = new Handler(Looper.getMainLooper());

    // =========================================================
    // PUBLIC API
    // =========================================================

    public static synchronized String start(Context ctx, String outName) {
        if (running) return "ALREADY";
        running = true;

        app = ctx.getApplicationContext();
        outFile = new File(app.getFilesDir(), "app/data/" + outName);

        JSONObject cfg = loadConfig();
        if (cfg == null) return fail("NO_CONFIG");

        if (!loadProfile(cfg)) return fail("NO_PROFILE");

        BluetoothAdapter ad = BluetoothAdapter.getDefaultAdapter();
        if (ad == null || !ad.isEnabled()) return fail("BT_OFF");

        device = ad.getRemoteDevice(targetMac);

        gatt = (Build.VERSION.SDK_INT >= 23)
                ? device.connectGatt(app, false, cb, BluetoothDevice.TRANSPORT_LE)
                : device.connectGatt(app, false, cb);

        Log.i(TAG, "started for " + targetMac);
        return "OK";
    }

    public static synchronized void stop() {
        running = false;

        try {
            if (gatt != null) {
                gatt.disconnect();
                gatt.close();
            }
        } catch (Throwable ignored) {}

        gatt = null;
        device = null;
        notifyChar = null;
        commandIndex = 0;

        Log.i(TAG, "stopped");
    }

    // =========================================================
    // CONFIG / PROFILE
    // =========================================================

    private static JSONObject loadConfig() {
        try {
            File f = new File(app.getFilesDir(), "app/data/log_config.json");
            if (!f.exists()) return null;
            return new JSONObject(readFile(f));
        } catch (Throwable t) {
            Log.e(TAG, "config load failed", t);
            return null;
        }
    }

    private static boolean loadProfile(JSONObject cfg) {
        try {
            JSONObject devs = cfg.getJSONObject("devices");
            Iterator<String> it = devs.keys();
            if (!it.hasNext()) return false;

            targetMac = it.next();
            String profName = devs.getJSONObject(targetMac).getString("bridge_profile");

            File pf = new File(app.getFilesDir(),
                    "app/data/bridge_profiles/" + profName + ".json");

            JSONObject p = new JSONObject(readFile(pf));

            serviceUuid = UUID.fromString(p.getString("service_uuid"));
            notifyUuid  = UUID.fromString(p.getString("notify_uuid"));
            commandUuid = UUID.fromString(p.getString("command_uuid")); // <--- NEU
            pollMode = "poll".equalsIgnoreCase(p.optString("read_mode", "notify"));
            pollIntervalMs = Math.max(200, p.optLong("read_interval_ms", 1500));

            if (p.has("command_sequence")) {
                JSONArray a = p.getJSONArray("command_sequence");
                commandSeq = new byte[a.length()][];
                for (int i = 0; i < a.length(); i++) {
                    commandSeq[i] = parseHex(a.getString(i));
                }
            } else {
                commandSeq = null;
            }

            return true;

        } catch (Throwable t) {
            Log.e(TAG, "profile load failed", t);
            return false;
        }
    }

    // =========================================================
    // GATT CALLBACK
    // =========================================================

    private static final BluetoothGattCallback cb = new BluetoothGattCallback() {

        @Override
        public void onConnectionStateChange(BluetoothGatt g, int s, int ns) {
            if (!running) return;

            if (ns == BluetoothProfile.STATE_CONNECTED) {
                g.discoverServices();
            } else if (ns == BluetoothProfile.STATE_DISCONNECTED) {
                stop();
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            if (!running || status != BluetoothGatt.GATT_SUCCESS) return;

            BluetoothGattService svc = g.getService(serviceUuid);
            if (svc == null) return;

            // 1. Lese-Kanal (fff6)
            notifyChar = svc.getCharacteristic(notifyUuid);
            
            // 2. Schreib-Kanal (fff8) - Wir holen die UUID aus dem JSON Profil
            // Du musst in loadProfile() commandUuid = UUID.fromString(p.getString("command_uuid")) ergänzen!
            commandChar = svc.getCharacteristic(commandUuid); 

            if (notifyChar == null) return;

            if (pollMode) {
                startPoll();
                // Beim Pollen können wir sofort anfangen zu schreiben
                triggerCommandSequence();
            } else {
                // WICHTIG: Erst Notify einschalten. 
                // Das Schreiben der Kommandos triggern wir erst im onDescriptorWrite!
                enableNotify(g);
            }
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int s) {
            if (s == BluetoothGatt.GATT_SUCCESS && 
                d.getUuid().equals(UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"))) {
                
                Log.i(TAG, "Notification aktiv, starte Sequenz...");
                triggerCommandSequence();
            }
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c, int s) {
            // Nachdem ein Kommando geschrieben wurde, kurz warten und das nächste senden
            if (s == BluetoothGatt.GATT_SUCCESS) {
                main.postDelayed(LogBridge::writeNextCommand, 200); // 200ms Pause zwischen Kommandos
            }
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            handleValue(c.getValue());
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic c, int s) {
            if (s == BluetoothGatt.GATT_SUCCESS) {
                handleValue(c.getValue());
            }
        }
    };

    // =========================================================
    // MODES
    // =========================================================

    private static void enableNotify(BluetoothGatt g) {
        g.setCharacteristicNotification(notifyChar, true);

        BluetoothGattDescriptor d = notifyChar.getDescriptor(
                UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"));

        if (d != null) {
            d.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
            g.writeDescriptor(d);
        }
    }

    private static void startPoll() {
        new Thread(() -> {
            while (running && gatt != null) {
                try {
                    gatt.readCharacteristic(notifyChar);
                    Thread.sleep(pollIntervalMs);
                } catch (Throwable ignored) {}
            }
        }, "GattPoll").start();
    }

    // =========================================================
    // COMMAND SEQUENCE
    // =========================================================
    private static void triggerCommandSequence() {
            if (commandSeq != null) {
                commandIndex = 0;
                writeNextCommand();
            }
        }

    private static void writeNextCommand() {
        // Sicherheitscheck: Wir brauchen gatt und die SCHREIB-Characteristic (fff8)
        if (!running || gatt == null || commandChar == null) {
            Log.w(TAG, "Write abgebrochen: Gatt oder CommandChar nicht bereit");
            return;
        }
        
        // Prüfen, ob wir am Ende der Liste sind
        if (commandIndex >= commandSeq.length) {
            Log.i(TAG, "Alle Kommandos der Sequenz gesendet.");
            return;
        }
    
        byte[] value = commandSeq[commandIndex];
        
        // Wert auf die Schreib-Characteristic setzen
        commandChar.setValue(value);
        
        // WICHTIG: Den Write-Typ explizit auf DEFAULT (With Response) setzen,
        // damit das onCharacteristicWrite-Event sicher ausgelöst wird.
        commandChar.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
    
        boolean success = gatt.writeCharacteristic(commandChar);
        
        if (success) {
            Log.d(TAG, "Kommando gesendet: (0x) " + toHex(value) + " an index " + commandIndex);
            commandIndex++;
        } else {
            Log.e(TAG, "Gatt.writeCharacteristic fehlgeschlagen bei index " + commandIndex);
            // Optional: Nach kurzem Delay erneut versuchen oder Index trotzdem erhöhen
        }
    }

    // =========================================================
    // LOGGING
    // =========================================================

    private static synchronized void handleValue(byte[] v) {
        try {
            JSONObject o = new JSONObject();
            o.put("address", device.getAddress());
            o.put("name", device.getName());
            o.put("gatt_raw", toHex(v));
            o.put("ts", System.currentTimeMillis());
    
            // HIER DIE ERWEITERUNG:
            // Wir speichern, welcher Befehl gerade aktiv war.
            // Da commandIndex nach dem Schreiben erhöht wurde, 
            // nehmen wir commandIndex - 1 für den aktuell beantworteten Befehl.
            if (commandSeq != null && commandIndex > 0) {
                int currentIdx = commandIndex - 1;
                o.put("cmd_idx", currentIdx);
                o.put("cmd_hex", toHex(commandSeq[currentIdx]));
            }
    
            log.put(o);
    
            FileOutputStream fos = new FileOutputStream(outFile, false);
            fos.write(log.toString(2).getBytes("UTF-8"));
            fos.close();
    
        } catch (Throwable ignored) {}
    }

    // =========================================================
    // UTILS
    // =========================================================

    private static String readFile(File f) throws Exception {
        FileInputStream fis = new FileInputStream(f);
        byte[] b = new byte[(int) f.length()];
        fis.read(b);
        fis.close();
        return new String(b, "UTF-8");
    }

    private static byte[] parseHex(String s) {
        s = s.replace(" ", "").toUpperCase(Locale.US);
        byte[] out = new byte[s.length() / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    private static String toHex(byte[] v) {
        StringBuilder sb = new StringBuilder();
        for (byte b : v) sb.append(String.format("%02X", b));
        return sb.toString();
    }

    private static String fail(String r) {
        running = false;
        Log.w(TAG, r);
        return r;
    }
}
