package com.local.comicreader;

import android.content.Context;
import android.os.Environment;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

final class AppSettings {
    static final String DEFAULT_MANIFEST =
            "https://raw.githubusercontent.com/declinekid-design/"
                    + "jmcomic-desktop-android/main/android/update-manifest.json";

    private final Context context;
    private final File dataDir;
    private final File downloadDir;
    private final File settingsFile;
    private JSONObject values;

    AppSettings(Context context) {
        this.context = context.getApplicationContext();
        this.dataDir = new File(this.context.getFilesDir(), "jmcomic");
        File external = this.context.getExternalFilesDir(
                Environment.DIRECTORY_DOWNLOADS
        );
        if (external == null) {
            external = new File(this.context.getFilesDir(), "downloads");
        }
        this.downloadDir = new File(external, "JMComic");
        this.settingsFile = new File(dataDir, "settings.json");
        ensureDirectories();
        values = read();
    }

    private void ensureDirectories() {
        dataDir.mkdirs();
        new File(dataDir, "logs").mkdirs();
        new File(dataDir, "updates").mkdirs();
        downloadDir.mkdirs();
    }

    private JSONObject defaults() {
        JSONObject result = new JSONObject();
        try {
            result.put("folder", downloadDir.getAbsolutePath());
            result.put("client", "api");
            result.put("image_threads", 10);
            result.put("chapter_threads", 4);
            result.put("proxy_mode", "system");
            result.put("proxy", "");
            result.put("image_suffix", JSONObject.NULL);
            result.put("naming", "id");
            result.put("pack_zip", true);
            result.put("delete_after_zip", true);
            result.put("theme", "system");
            result.put("update_manifest_url", DEFAULT_MANIFEST);
            result.put("auto_check_update", true);
        } catch (JSONException ignored) {
        }
        return result;
    }

    private JSONObject read() {
        JSONObject result = defaults();
        if (!settingsFile.isFile()) {
            return result;
        }
        try (InputStream stream = new FileInputStream(settingsFile)) {
            byte[] data = new byte[(int) settingsFile.length()];
            int offset = 0;
            while (offset < data.length) {
                int read = stream.read(data, offset, data.length - offset);
                if (read < 0) {
                    break;
                }
                offset += read;
            }
            JSONObject saved = new JSONObject(
                    new String(data, 0, offset, StandardCharsets.UTF_8)
            );
            java.util.Iterator<String> keys = saved.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                result.put(key, saved.get(key));
            }
        } catch (IOException | JSONException ignored) {
        }
        result.remove("folder");
        try {
            result.put("folder", downloadDir.getAbsolutePath());
        } catch (JSONException ignored) {
        }
        return result;
    }

    void save() {
        try (FileOutputStream stream = new FileOutputStream(settingsFile)) {
            stream.write(
                    values.toString(2).getBytes(StandardCharsets.UTF_8)
            );
        } catch (IOException | JSONException ignored) {
        }
    }

    File dataDir() {
        return dataDir;
    }

    File downloadDir() {
        return downloadDir;
    }

    File updateDir() {
        File result = new File(dataDir, "updates");
        result.mkdirs();
        return result;
    }

    String getString(String key, String fallback) {
        String value = values.optString(key, fallback);
        return value == null ? fallback : value;
    }

    int getInt(String key, int fallback) {
        return Math.max(values.optInt(key, fallback), 1);
    }

    boolean getBoolean(String key, boolean fallback) {
        return values.optBoolean(key, fallback);
    }

    void set(String key, Object value) {
        try {
            values.put(key, value);
        } catch (JSONException ignored) {
        }
    }

    JSONObject pythonConfig() {
        JSONObject result = new JSONObject();
        try {
            result.put("data_dir", dataDir.getAbsolutePath());
            result.put("download_dir", downloadDir.getAbsolutePath());
            result.put("folder", downloadDir.getAbsolutePath());
            result.put("client", getString("client", "api"));
            result.put("image_threads", getInt("image_threads", 10));
            result.put("chapter_threads", getInt("chapter_threads", 4));
            result.put("proxy_mode", getString("proxy_mode", "system"));
            result.put("proxy", getString("proxy", ""));
            Object suffix = values.opt("image_suffix");
            result.put(
                    "image_suffix",
                    suffix == null || suffix == JSONObject.NULL ? "" : suffix
            );
            result.put("naming", getString("naming", "id"));
            result.put("pack_zip", getBoolean("pack_zip", true));
            result.put(
                    "delete_after_zip",
                    getBoolean("delete_after_zip", true)
            );
            result.put("theme", getString("theme", "system"));
            result.put(
                    "update_manifest_url",
                    getString("update_manifest_url", DEFAULT_MANIFEST)
            );
            result.put("current_version", BuildConfig.VERSION_NAME);
        } catch (JSONException ignored) {
        }
        return result;
    }
}
