package org.hackintosh1980.blebridge;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.UUID;

public class GattBridge {

    private static final String TAG = "GattBridge";
    private static final long WRITE_INTERVAL_MS = 1200L;

    private static int COMPANY_ID = 0x0019;

    private static final UUID CCCD_UUID =
            UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private static final Handler mainHandler = new Handler(Looper.getMainLooper());

    private static volatile boolean running = false;

    // POLL mode
    private static boolean pollEnabled = false;
    private static long pollIntervalMs = 1500;

    // GATT State
    private static BluetoothGatt gatt;
    private static BluetoothDevice gattDevice;
    private static boolean gattActive = false;

    // config/profile driven
    private static String targetMac = null;
    private static String profileName = null;

    private static UUID serviceUuid = null;
    private static UUID notifyUuid = null;      // required
    private static UUID commandUuid = null;     // optional
    private static byte[] commandBytes = null;  // optional
    private static long lastGattRx = 0;

    private static BluetoothGattCharacteristic notifyChar = null;
    private static BluetoothGattCharacteristic cmdChar = null;

    private static int gattCounter = 0;
    private static Context appContext;

    private static File outFile;
    private static File getAppDataDir(Context ctx) {
        // EINZIGE WAHRHEIT für Android-Pipeline-Daten
        return new File(ctx.getFilesDir(), "app/data");
    }
    // poll thread guard
    private static Thread pollThread = null;

    // ---------------------------------------------------------------------
    // Timestamp + Hex helpers
    // ---------------------------------------------------------------------
    private static String ts() {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US);
        sdf.setTimeZone(TimeZone.getDefault());
        return sdf.format(new Date());
    }

    private static String toHex(byte[] v) {
        if (v == null) return "";
        StringBuilder sb = new StringBuilder();
        for (byte b : v) sb.append(String.format("%02X", b));
        return sb.toString();
    }

    private static byte[] parseHex(String hex) {
        if (hex == null) return null;
        hex = hex.replace(" ", "").trim();
        if (hex.isEmpty()) return null;
        if ((hex.length() % 2) != 0) return null;

        byte[] out = new byte[hex.length() / 2];
        for (int i = 0; i < out.length; i++) {
            int hi = Character.digit(hex.charAt(i * 2), 16);
            int lo = Character.digit(hex.charAt(i * 2 + 1), 16);
            if (hi < 0 || lo < 0) return null;
            out[i] = (byte) ((hi << 4) | lo);
        }
        return out;
    }

    private static String readTextFile(File f) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        FileInputStream fis = new FileInputStream(f);
        try {
            byte[] buf = new byte[4096];
            int n;
            while ((n = fis.read(buf)) > 0) bos.write(buf, 0, n);
        } finally {
            try { fis.close(); } catch (Throwable ignore) {}
        }
        return bos.toString("UTF-8");
    }

    private static String cleanNullableString(JSONObject p, String key) {
        try {
            String v = p.optString(key, null);
            if (v == null) return null;
            v = v.trim();
            if (v.isEmpty()) return null;
            if ("null".equalsIgnoreCase(v)) return null;
            return v;
        } catch (Throwable ignore) {
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // CONFIG + PROFILE
    // -----------------------------------------------------------------------
    private static JSONObject loadConfig(Context ctx) {
        try {
            File cfg = new File(getAppDataDir(ctx), "gatt_config.json");
            if (!cfg.exists()) {
                Log.w(TAG, "config.json not found: " + cfg.getAbsolutePath());
                return null;
            }
            return new JSONObject(readTextFile(cfg));
        } catch (Throwable t) {
            Log.e(TAG, "config load failed", t);
            return null;
        }
    }

    private static JSONObject loadBridgeProfile(Context ctx, String profName) {
        try {
            File prof = new File(
                new File(getAppDataDir(ctx), "bridge_profiles"),
                profName + ".json"
            );

            if (!prof.exists()) {
                Log.w(TAG, "bridge profile not found: " + prof.getAbsolutePath());
                return null;
            }
            return new JSONObject(readTextFile(prof));
        } catch (Throwable t) {
            Log.e(TAG, "bridge profile load", t);
            return null;
        }
    }

    private static void parseBridgeProfile(JSONObject p) {
        serviceUuid = null;
        notifyUuid = null;
        commandUuid = null;
        commandBytes = null;

        pollEnabled = false;
        pollIntervalMs = 1500;

        COMPANY_ID = 0x0019;

        if (p == null) return;

        try {
            String su = cleanNullableString(p, "service_uuid");
            String nu = cleanNullableString(p, "notify_uuid");
            String cu = cleanNullableString(p, "command_uuid");
            String cmd = cleanNullableString(p, "command");

            if (su != null) serviceUuid = UUID.fromString(su);
            if (nu != null) notifyUuid = UUID.fromString(nu);
            if (cu != null) commandUuid = UUID.fromString(cu);
            if (cmd != null) commandBytes = parseHex(cmd);

            String rm = cleanNullableString(p, "read_mode");
            pollEnabled = "poll".equalsIgnoreCase(rm);

            if (p.has("read_interval_ms")) {
                pollIntervalMs = Math.max(200, p.optLong("read_interval_ms", 1500));
            }

            if (p.has("company_id")) {
                try {
                    Object v = p.get("company_id");
                    if (v instanceof Number) {
                        COMPANY_ID = ((Number) v).intValue() & 0xFFFF;
                    } else if (v instanceof String) {
                        String s = ((String) v).trim().toLowerCase(Locale.US);
                        if (s.startsWith("0x")) COMPANY_ID = Integer.parseInt(s.substring(2), 16) & 0xFFFF;
                        else COMPANY_ID = Integer.parseInt(s) & 0xFFFF;
                    }
                } catch (Throwable ignore) {}
            }

            if (notifyUuid == null) Log.e(TAG, "notify_uuid missing in profile!");
        } catch (Throwable t) {
            Log.e(TAG, "profile parse", t);
        }
    }

    private static void initFromConfigAndProfile(Context ctx, JSONObject cfg) {
        targetMac = null;
        profileName = null;

        try {
            JSONObject devs = cfg.getJSONObject("devices");
            Iterator<String> it = devs.keys();
            if (it.hasNext()) {
                String mac = it.next();
                JSONObject devCfg = devs.getJSONObject(mac);
                targetMac = mac;
                profileName = devCfg.optString("bridge_profile", null);
                Log.i(TAG, "Config device: " + targetMac + " bridge_profile=" + profileName);
            }
        } catch (Throwable t) {
            Log.e(TAG, "Config parse error", t);
        }

        if (profileName != null && profileName.trim().length() > 0) {
            JSONObject prof = loadBridgeProfile(ctx, profileName);
            parseBridgeProfile(prof);
        } else {
            Log.w(TAG, "No bridge_profile set in config (GATT disabled).");
        }

        try {
            if (targetMac != null) {
                BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
                if (adapter != null) {
                    gattDevice = adapter.getRemoteDevice(targetMac);
                }
            }
        } catch (Throwable t) {
            Log.e(TAG, "getRemoteDevice failed", t);
            gattDevice = null;
        }
    }

    // ---------------------------------------------------------------------
    // START / STOP
    // ---------------------------------------------------------------------
    public static String start(Context ctx, String outName) {
        if (running) return "ALREADY";
        running = true;
        appContext = ctx.getApplicationContext();
        // runtime reset
        gatt = null;
        gattActive = false;

        notifyChar = null;
        cmdChar = null;

        pollThread = null;

        gattCounter = 0;
        COMPANY_ID = 0x0019;

        outFile = new File(getAppDataDir(ctx), outName);


        JSONObject cfg = loadConfig(ctx);
        if (cfg == null) {
            Log.w(TAG, "No config – GATT disabled.");
            running = false;
            return "NO_CONFIG";
        }

        initFromConfigAndProfile(ctx, cfg);

        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null || !adapter.isEnabled()) {
            running = false;
            return "BT_OFF";
        }

        if (gattDevice == null || notifyUuid == null) {
            Log.w(TAG, "GattBridge not started (missing device/notifyUuid)");
            running = false;
            return "NO_TARGET";
        }

        Log.i(TAG, "GattBridge starting… poll=" + pollEnabled + " interval=" + pollIntervalMs + "ms");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            gatt = gattDevice.connectGatt(ctx, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
        } else {
            gatt = gattDevice.connectGatt(ctx, false, gattCallback);
        }

        gattActive = true;

        // writer thread – schreibt gemeinsamen ADV+GATT Store
        new Thread(() -> {
            while (running && gattActive) {
                try {
                    JSONArray arr;
                    synchronized (AdvBridge.getLock()) {
                        arr = new JSONArray(AdvBridge.getStore().values());
                    }

                    File tmp = new File(outFile.getAbsolutePath() + ".tmp");
                    try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                        fos.write(arr.toString(2).getBytes("UTF-8"));
                    }
                    //noinspection ResultOfMethodCallIgnored
                    tmp.renameTo(outFile);

                    Thread.sleep(WRITE_INTERVAL_MS);
                } catch (Throwable t) {
                    Log.e(TAG, "writer", t);
                }
            }
        }, "GattWriter").start();

        // command keeper – hält Geräte mit command aktiv (notify-mode devices)
        new Thread(() -> {
            while (running && gattActive) {
                try {
                    long now = System.currentTimeMillis();
                    if (commandBytes != null && commandBytes.length > 0) {
                        if (now - lastGattRx > 3000) {
                            if (gatt != null) {
                                writeCommand(gatt);
                            }
                        }
                    }
                    Thread.sleep(1000);
                } catch (Throwable ignored) {}
            }
        }, "GattCommandKeeper").start();

        return "OK";
    }

    public static void stop() {
        running = false;
        gattActive = false;
    
        closeGattHard();
    
        Log.i(TAG, "GattBridge stopped");
    }

    // ---------------------------------------------------------------------
    // internal close + command
    // ---------------------------------------------------------------------
    // SOFT close = Reconnect erlaubt (aber sauber!)
    private static void closeGattSoft(BluetoothGatt g) {
        // stop loops that depend on gattActive
        gattActive = false;
    
        try {
            if (g != null) {
                try { g.disconnect(); } catch (Throwable ignored) {}
                try { g.close(); } catch (Throwable ignored) {}
            }
        } catch (Throwable ignored) {}
    
        gatt = null;
    
        notifyChar = null;
        cmdChar = null;
    
        // poll thread will naturally exit because gattActive=false
        pollThread = null;
    
        lastGattRx = 0;
    }
    // HARD close = Gerätewechsel / kompletter Reset
    private static void closeGattHard() {
        try {
            if (gatt != null) gatt.close();
        } catch (Throwable ignored) {}
    
        gatt = null;
        gattDevice = null;
        gattActive = false;
    
        notifyChar = null;
        cmdChar = null;
        pollThread = null;
    }

    private static void writeCommand(BluetoothGatt g) {
        if (cmdChar != null && commandBytes != null && commandBytes.length > 0) {
            try {
                cmdChar.setValue(commandBytes);
                boolean ok = g.writeCharacteristic(cmdChar);
                Log.i(TAG, "Command write: " + ok + " cmd=" + toHex(commandBytes));
            } catch (Throwable t) {
                Log.e(TAG, "Command write error", t);
            }
        } else {
            Log.i(TAG, "No command (notify-only)");
        }
    }
    private static void scheduleReconnect() {
        if (!running || gattDevice == null) return;
    
        Log.i(TAG, "GattBridge: reconnect attempt");
    
        mainHandler.postDelayed(() -> {
            if (!running || gattDevice == null) return;
    
            // mark active for loops again (writer/keeper are guarded by running && gattActive)
            gattActive = true;
    
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                gatt = gattDevice.connectGatt(
                        appContext,
                        false,
                        gattCallback,
                        BluetoothDevice.TRANSPORT_LE
                );
            } else {
                gatt = gattDevice.connectGatt(appContext, false, gattCallback);
            }
        }, 400);
    }
    // ---------------------------------------------------------------------
    // CENTRAL VALUE HANDLER (write gatt_raw + packet_counter)
    // ---------------------------------------------------------------------
    private static void handleGattValue(BluetoothGatt g, byte[] v) {
        if (v == null || v.length == 0) return;

        BluetoothDevice dev = (g != null) ? g.getDevice() : null;
        if (dev == null) return;

        lastGattRx = System.currentTimeMillis();

        String addr = dev.getAddress();
        String name = (dev.getName() != null) ? dev.getName() : "(gatt)";
        String rawNative = toHex(v);

        gattCounter = (gattCounter + 1) & 0xFF;
        // ignore warmup/empty payloads (all-zero)
        boolean allZero = true;
        for (byte x : v) {
            if (x != 0x00) { allZero = false; break; }
        }
        if (allZero) {
            // keep alive/reconnect logic running, but DO NOT overwrite last good payload
            lastGattRx = System.currentTimeMillis();
            return;
        }
        synchronized (AdvBridge.getLock()) {
            Map<String, JSONObject> store = AdvBridge.getStore();
            JSONObject obj = store.get(addr);

            try {
                if (obj == null) {
                    obj = new JSONObject();
                    obj.put("address", addr);
                    obj.put("name", name);
                    obj.put("rssi", 0);
                    obj.put("adv_raw", JSONObject.NULL);
                } else {
                    obj.put("name", name);
                    if (!obj.has("adv_raw")) obj.put("adv_raw", JSONObject.NULL);
                }

                obj.put("gatt_raw", rawNative);
                obj.put("packet_counter", gattCounter);
                obj.put("timestamp", ts());

                store.put(addr, obj);
            } catch (Throwable ignored) {}
        }
    }

    // -----------------------------------------------------------------------
    // GATT CALLBACK
    // -----------------------------------------------------------------------
    private static final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {

        @Override
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            Log.i(TAG, "onConnectionStateChange: status=" + status + " newState=" + newState);

            if (newState == BluetoothProfile.STATE_CONNECTED) {
                Log.i(TAG, "GATT connected → discover services");
                mainHandler.postDelayed(g::discoverServices, 150);
                return;
            }
            
            if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                Log.w(TAG, "GATT disconnected → soft close + reconnect");
                closeGattSoft(g);
                scheduleReconnect();
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            Log.i(TAG, "onServicesDiscovered: status=" + status);
        
            if (status != BluetoothGatt.GATT_SUCCESS || notifyUuid == null) {
                Log.e(TAG, "Service discovery failed");
                closeGattSoft(g);
                scheduleReconnect();
                return;
            }
        
            notifyChar = null;
            cmdChar = null;
        
            // 1) Characteristic suchen (Service bevorzugt)
            if (serviceUuid != null) {
                BluetoothGattService s = g.getService(serviceUuid);
                if (s != null) {
                    notifyChar = s.getCharacteristic(notifyUuid);
                    if (commandUuid != null) {
                        cmdChar = s.getCharacteristic(commandUuid);
                    }
                }
            }
        
            // 2) Fallback: global suchen
            if (notifyChar == null || (commandUuid != null && cmdChar == null)) {
                for (BluetoothGattService s : g.getServices()) {
                    for (BluetoothGattCharacteristic c : s.getCharacteristics()) {
                        if (notifyChar == null && c.getUuid().equals(notifyUuid)) {
                            notifyChar = c;
                        }
                        if (commandUuid != null && cmdChar == null && c.getUuid().equals(commandUuid)) {
                            cmdChar = c;
                        }
                    }
                }
            }
        
            if (notifyChar == null) {
                Log.e(TAG, "Characteristic not found: " + notifyUuid);
                closeGattSoft(g);
                scheduleReconnect();
                return;
            }
        
            // 3) POLL MODE
            if (pollEnabled) {
                Log.i(TAG, "POLL mode enabled @" + pollIntervalMs + "ms");
        
                if (pollThread == null) {
                    pollThread = new Thread(() -> {
                        while (running && gattActive) {
                            try {
                                BluetoothGatt gg = gatt;
                                BluetoothGattCharacteristic cc = notifyChar;
                                if (gg != null && cc != null) {
                                    gg.readCharacteristic(cc);
                                }
                                Thread.sleep(pollIntervalMs);
                            } catch (Throwable ignored) {}
                        }
                    }, "GattReadPoll");
                    pollThread.start();
                }
                return;
            }
        
            // 4) NOTIFY MODE
            boolean ok = g.setCharacteristicNotification(notifyChar, true);
            Log.i(TAG, "setCharacteristicNotification: " + ok);
        
            BluetoothGattDescriptor cccd = notifyChar.getDescriptor(CCCD_UUID);
            if (cccd != null) {
                byte[] value;
                int props = notifyChar.getProperties();
        
                if ((props & BluetoothGattCharacteristic.PROPERTY_INDICATE) != 0) {
                    value = BluetoothGattDescriptor.ENABLE_INDICATION_VALUE;
                } else {
                    value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE;
                }
        
                cccd.setValue(value);
                boolean dOk = g.writeDescriptor(cccd);
                Log.i(TAG, "writeDescriptor(CCCD): " + dOk);
        
                if (!dOk) writeCommand(g);
            } else {
                writeCommand(g);
            }
        }
        @Override
        public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor descriptor, int status) {
            if (descriptor != null && CCCD_UUID.equals(descriptor.getUuid())) {
                Log.i(TAG, "onDescriptorWrite(CCCD): status=" + status);
                writeCommand(g);
            }
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt g, BluetoothGattCharacteristic ch, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS || ch == null) return;
            handleGattValue(g, ch.getValue());
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic ch) {
            if (ch == null) return;
            handleGattValue(g, ch.getValue());
        }
    };
}
