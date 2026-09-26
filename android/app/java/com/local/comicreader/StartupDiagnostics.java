package com.local.comicreader;

import android.app.Application;
import android.content.Context;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

final class StartupDiagnostics {
    private static final String TAG = "JMComicStartup";
    private static final String FILE_NAME = "startup.log";

    private StartupDiagnostics() {
    }

    static void install(Application application) {
        Thread.UncaughtExceptionHandler previous =
                Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            record(application, "FATAL thread=" + thread.getName(), error);
            if (previous != null) {
                previous.uncaughtException(thread, error);
            }
        });
    }

    static void record(Context context, String message) {
        record(context, message, null);
    }

    static void record(Context context, String message, Throwable error) {
        String suffix = "";
        if (error != null) {
            StringWriter buffer = new StringWriter();
            error.printStackTrace(new PrintWriter(buffer));
            suffix = "\n" + buffer;
        }
        String timestamp = new SimpleDateFormat(
                "yyyy-MM-dd HH:mm:ss.SSS",
                Locale.US
        ).format(new Date());
        String line = timestamp + " " + message + suffix + "\n";
        Log.e(TAG, line);
        write(context.getFilesDir(), line);
        File external = context.getExternalFilesDir(null);
        if (external != null) {
            write(external, line);
        }
    }

    static String read(Context context) {
        File internal = new File(context.getFilesDir(), FILE_NAME);
        if (!internal.isFile()) {
            return "";
        }
        try {
            byte[] data = java.nio.file.Files.readAllBytes(internal.toPath());
            return new String(data, StandardCharsets.UTF_8);
        } catch (IOException error) {
            return "";
        }
    }

    private static void write(File directory, String line) {
        if (!directory.exists() && !directory.mkdirs()) {
            return;
        }
        File file = new File(directory, FILE_NAME);
        try (FileOutputStream output = new FileOutputStream(file, true)) {
            output.write(line.getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
        }
    }
}
