package org.hackintosh1980.blebridge;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.le.*;
import android.content.Context;
import android.os.ParcelUuid;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.UUID;

public class BroadcastBridge {
    private static BluetoothLeAdvertiser advertiser;
    private static AdvertiseCallback activeCallback; 
    private static Thread loopThread;
    private static boolean running = false;
    private static String mixedPath;
    private static Context appContext;
    private static byte[] lastPayload = new byte[0];
    private static int packetCounter = 0;

    public static synchronized boolean start(Context ctx, String path) {
        if (running) return true;
        
        appContext = ctx.getApplicationContext();
        mixedPath = path;
        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null || !adapter.isEnabled()) return false;

        advertiser = adapter.getBluetoothLeAdvertiser();
        if (advertiser == null) return false;

        running = true;
        loopThread = new Thread(() -> loop());
        loopThread.start();
        return true;
    }

    public static synchronized void stop() {
        running = false;
        if (loopThread != null) {
            loopThread.interrupt();
            loopThread = null;
        }
        stopActiveAdvertising();
    }

    private static void stopActiveAdvertising() {
        if (advertiser != null && activeCallback != null) {
            try {
                advertiser.stopAdvertising(activeCallback);
            } catch (Exception ignored) {}
            activeCallback = null;
        }
    }

    private static long lastAdvertiseTime = 0;
    
    private static void loop() {
    
        while (running) {
    
            try {
    
                byte[] currentPayload = encodeMixed();
                long now = System.currentTimeMillis();
    
                boolean payloadChanged = !Arrays.equals(currentPayload, lastPayload);
                boolean watchdog = (now - lastAdvertiseTime) > 20000;
    
                if (currentPayload.length > 0 && (payloadChanged || watchdog)) {
    
                    stopActiveAdvertising();
                    advertise(currentPayload);
    
                    lastPayload = currentPayload;
                    lastAdvertiseTime = now;
    
                    Log.i("BroadcastBridge", "Advertising refreshed");
                }
    
                Thread.sleep(5000);
    
            } catch (InterruptedException e) {
                break;
            } catch (Exception e) {
                Log.e("BroadcastBridge", "Loop Error", e);
            }
        }
    }

    private static void advertise(byte[] payload) {
        activeCallback = new AdvertiseCallback() {
            @Override
            public void onStartSuccess(AdvertiseSettings settingsInEffect) {
                super.onStartSuccess(settingsInEffect);
                Log.i("BroadcastBridge", "Advertising active");
            }
        };
        
        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter != null) {
            adapter.setName("LGS");
        }

        ParcelUuid pUuid = new ParcelUuid(UUID.fromString("0000181A-0000-1000-8000-00805f9b34fb"));
    
        AdvertiseData data = new AdvertiseData.Builder()
                .addServiceUuid(pUuid)
                .addManufacturerData(17780, payload) // DEINE FESTE ID 17780
                .setIncludeDeviceName(true)
                .build();
    
        AdvertiseSettings settings = new AdvertiseSettings.Builder()
                .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
                .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
                .setConnectable(false)
                .setTimeout(0)
                .build();
        
        try {
            advertiser.startAdvertising(settings, data, activeCallback);
        } catch (Exception e) {
            Log.e("BroadcastBridge", "Start Advertising failed", e);
        }
    }

    private static byte[] encodeMixed() {
        try {
            // 1. Kanal aus config.json laden
            int sendChannel = 17;
            try {
                File cfgFile = new File(appContext.getFilesDir(), "app/data/config.json");
                if (cfgFile.exists()) {
                    String cfgTxt = new String(Files.readAllBytes(cfgFile.toPath()));
                    JSONObject cfgJson = new JSONObject(cfgTxt);
                    sendChannel = cfgJson.optInt("lgs_mesh_channel_send", 17);
                }
            } catch (Exception e) {
                Log.w("BroadcastBridge", "Config load failed, using 17");
            }

            // 2. Sensordaten laden
            File f = new File(mixedPath);
            if (!f.exists()) return new byte[0];
            String txt = new String(Files.readAllBytes(f.toPath()));
            JSONArray arr = new JSONArray(txt);
            if (arr.length() == 0) return new byte[0];
            JSONObject obj = arr.getJSONObject(0);

            int t = (int)(obj.optDouble("avg_temp", 0) * 100);
            int h = (int)(obj.optDouble("avg_hum", 0) * 100);
            int v = (int)(obj.optDouble("avg_vpd", 0) * 100);

            // --- SCHLANKE PAYLOAD OHNE VPD ---
            byte[] data = new byte[7];
            data[0] = (byte) 0xA1;
            data[1] = (byte) (sendChannel & 0xFF);
            
            // Temperatur (2 Bytes)
            data[2] = (byte) ((t >> 8) & 0xFF); 
            data[3] = (byte) (t & 0xFF);
            
            // Feuchtigkeit (2 Bytes)
            data[4] = (byte) ((h >> 8) & 0xFF); 
            data[5] = (byte) (h & 0xFF);
            
            // Counter (1 Byte) - Jetzt an Position 6
            packetCounter = (packetCounter + 1) % 256; 
            data[6] = (byte) (packetCounter & 0xFF);

            return data;
        } catch (Exception e) { 
            return new byte[0]; 
        }
    }
}