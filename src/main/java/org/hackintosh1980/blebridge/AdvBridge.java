package org.hackintosh1980.blebridge;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.le.*;
import android.content.Context;
import android.util.Log;
import android.util.SparseArray;
import java.util.List;
import java.util.ArrayList;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Map;
import java.util.HashMap;
import java.util.TimeZone;

public class AdvBridge {

    private static final String TAG = "AdvBridge";
    private static final long WRITE_INTERVAL_MS = 1200L;
    private static final int RSSI_MIN = -127; 

    private static volatile boolean running = false;
    private static volatile long lastPacketTime = 0L;
    private static BluetoothLeScanner scanner;
    private static ScanCallback callback;

    private static File outFile;

    private static final Object lock = new Object();
    private static final Map<String, JSONObject> last = new HashMap<>();

    // -------------------- Helpers --------------------
    private static String ts() {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US);
        sdf.setTimeZone(TimeZone.getDefault());
        return sdf.format(new Date());
    }

    private static File getAppDataDir(Context ctx) {
        return new File(ctx.getFilesDir(), "app/data");
    }

    private static String toHex(byte[] v) {
        if (v == null || v.length == 0) return null;
        StringBuilder sb = new StringBuilder();
        for (byte b : v) sb.append(String.format("%02X", b));
        return sb.toString();
    }

    private static String readTextFile(File f) throws Exception {
        if (!f.exists()) return "{}";
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (FileInputStream fis = new FileInputStream(f)) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = fis.read(buf)) > 0) bos.write(buf, 0, n);
        }
        return bos.toString("UTF-8");
    }

    // -------------------- Watchdog --------------------
    private static Thread scanWatchdog;
    
    private static void startScanWatchdog(Context ctx, BluetoothAdapter adapter) {
        if (scanWatchdog != null && scanWatchdog.isAlive()) return;
    
        scanWatchdog = new Thread(() -> {
            lastPacketTime = System.currentTimeMillis();
    
            while (running) {
                try {
                    android.os.SystemClock.sleep(2000);
                    long now = System.currentTimeMillis();
    
                    if (now - lastPacketTime > 3500) {
                        Log.w(TAG, "Watchdog: Restarting Scan...");
    
                        BluetoothLeScanner freshScanner = adapter.getBluetoothLeScanner();
    
                        if (freshScanner != null && callback != null) {
    
                            try {
                                if (scanner != null) {
                                    scanner.stopScan(callback);
                                }
                            } catch (Throwable ignore) {}
    
                            Thread.sleep(150);
    
                            ScanSettings settings = new ScanSettings.Builder()
                                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                                    .setCallbackType(ScanSettings.CALLBACK_TYPE_ALL_MATCHES)
                                    .setMatchMode(ScanSettings.MATCH_MODE_AGGRESSIVE)
                                    .setNumOfMatches(ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT)
                                    .build();
    
                            List<ScanFilter> filters = new ArrayList<>();
                            filters.add(new ScanFilter.Builder().build());
    
                            try {
                                freshScanner.startScan(filters, settings, callback);
                                scanner = freshScanner;
                                lastPacketTime = System.currentTimeMillis();
                            } catch (Throwable t) {
                                Log.e(TAG, "Watchdog Restart failed", t);
                            }
                        }
                    }
    
                } catch (InterruptedException e) {
                    break;
                }
            }
    
        }, "AdvScanWatchdog");
    
        scanWatchdog.setDaemon(true);
        scanWatchdog.start();
    }

    private static void loadExistingSnapshot() {
        try {
            if (outFile == null || !outFile.exists()) return;
            String txt = readTextFile(outFile).trim();
            if (txt.isEmpty() || txt.equals("{}")) return;
            JSONArray arr = new JSONArray(txt);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o != null && o.has("address")) {
                    last.put(o.getString("address"), o);
                }
            }
        } catch (Throwable t) { Log.w(TAG, "Preload failed", t); }
    }

    private static void writeSnapshot() {
        try {
            JSONArray arr = new JSONArray(last.values());
            File tmp = new File(outFile.getAbsolutePath() + ".tmp");
            try (FileOutputStream fos = new FileOutputStream(tmp, false)) {
                fos.write(arr.toString(2).getBytes("UTF-8"));
                fos.flush();
            }
            tmp.renameTo(outFile);
        } catch (Throwable t) { Log.e(TAG, "writer", t); }
    }

    // -------------------- API --------------------
    public static String start(Context ctx) {
        if (running) return "ALREADY";

        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null || !adapter.isEnabled()) return "BT_OFF";

        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) return "NO_SCANNER";

        outFile = new File(getAppDataDir(ctx), "ble_dump.json");

        synchronized (lock) {
            loadExistingSnapshot();
        }

        running = true;
        
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .setReportDelay(0)
                .build();

        callback = new ScanCallback() {
            @Override
            public void onScanResult(int type, ScanResult r) {
                if (!running) return;
                lastPacketTime = System.currentTimeMillis(); 
              
                try {
                    if (r == null || r.getDevice() == null) return;
                    if (r.getRssi() < RSSI_MIN) return;
        
                    ScanRecord rec = r.getScanRecord();
                    if (rec == null) return;

                    String mac  = r.getDevice().getAddress();
                    String raw = null;

                    // 1) Manufacturer Data auslesen
                    SparseArray<byte[]> md = rec.getManufacturerSpecificData();
                    if (md != null && md.size() > 0) {
                        for (int i = 0; i < md.size(); i++) {
                            int companyId = md.keyAt(i);
                            byte[] payload = md.valueAt(i);
                            ByteArrayOutputStream bos = new ByteArrayOutputStream();
                            bos.write(companyId & 0xFF);
                            bos.write((companyId >> 8) & 0xFF);
                            if (payload != null) bos.write(payload);
                            raw = toHex(bos.toByteArray());
                            break;
                        }
                    }

                    if (raw == null) return;

                    // --- NEU: Definitionen für den Compiler ---
                    String devName = rec.getDeviceName();
                    if (devName == null) devName = r.getDevice().getName();
                    if (devName == null) devName = "Unknown";
                    int currentRssi = r.getRssi();
                    // ------------------------------------------

                    synchronized (lock) {
                        int recvChannel = 17; 
                        try {
                            File cfgFile = new File(getAppDataDir(ctx), "config.json");
                            JSONObject cfg = new JSONObject(readTextFile(cfgFile));
                            recvChannel = cfg.optInt("lgs_mesh_channel_recv", 17);
                        } catch (Exception e) { /* Fallback 17 */ }
                    
                        if (raw.startsWith("7445")) {
                            String targetSignature = String.format("7445A1%02X", recvChannel);
                            
                            if (raw.startsWith(targetSignature)) {
                                String effectiveMac = "FF:FF:A1:00:00:01";
                                if (!effectiveMac.equals(mac)) {
                                    last.remove(mac);
                                }
                                JSONObject obj = last.get(effectiveMac);
                                if (obj == null) {
                                    obj = new JSONObject();
                                    obj.put("address", effectiveMac);
                                    obj.put("gatt_raw", JSONObject.NULL);
                                }
                                obj.put("timestamp", ts());
                                obj.put("name", "LGS_NODE_" + recvChannel);
                                obj.put("rssi", currentRssi);
                                obj.put("adv_raw", raw);
                                obj.put("log_raw", raw);
                                obj.put("note", "active_mesh_ch_" + recvChannel);
                                last.put(effectiveMac, obj);
                            } else {
                                last.remove(mac);
                                return; 
                            }
                        } else {
                            // FALL C: Ein ganz anderes Gerät (Variablen korrigiert)
                            JSONObject obj = last.get(mac);
                            if (obj == null) {
                                obj = new JSONObject();
                                obj.put("address", mac);
                                obj.put("gatt_raw", JSONObject.NULL);
                            }
                            obj.put("timestamp", ts());
                            obj.put("name", devName);
                            obj.put("rssi", currentRssi);
                            obj.put("adv_raw", raw);
                            obj.put("log_raw", raw);
                            obj.put("note", "raw");
                            last.put(mac, obj);
                        }
                    }
                    // --- ENDE DES KORREKTUR-BLOCKS ---
                } catch (Throwable t) { Log.e(TAG, "scan", t); }
            }
        };

        List<ScanFilter> filters = new ArrayList<>();
        filters.add(new ScanFilter.Builder().build());
        
        startScanWatchdog(ctx, adapter);
        
        try {
            scanner.startScan(filters, settings, callback);
        } catch (Throwable t) {
            running = false;
            return "ERR_SCAN";
        }

        new Thread(() -> {
            while (running) {
                try {
                    synchronized (lock) { writeSnapshot(); }
                    Thread.sleep(WRITE_INTERVAL_MS);
                } catch (Throwable t) { Log.e(TAG, "writerLoop", t); }
            }
        }, "AdvWriter").start();

        return "OK";
    }

    public static void stop() {
        running = false;
        try { if (scanner != null && callback != null) scanner.stopScan(callback); } catch (Throwable ignore) {}
        try { if (scanWatchdog != null) scanWatchdog.interrupt(); } catch (Throwable ignore) {}
        Log.i(TAG, "ADV stopped");
    }

    // Erforderlich für GattBridge Synchronisation
    public static Object getLock() { 
        return lock; 
    }

    public static Map<String, JSONObject> getStore() { 
        return last; 
    }
}