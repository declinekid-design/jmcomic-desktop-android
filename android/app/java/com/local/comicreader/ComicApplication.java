package com.local.comicreader;

import com.chaquo.python.android.PyApplication;

public final class ComicApplication extends PyApplication {
    @Override
    public void onCreate() {
        StartupDiagnostics.install(this);
        StartupDiagnostics.record(this, "Application.onCreate begin");
        try {
            super.onCreate();
            StartupDiagnostics.record(this, "PyApplication.onCreate complete");
        } catch (RuntimeException | Error error) {
            StartupDiagnostics.record(this, "PyApplication.onCreate failed", error);
            throw error;
        }
    }
}
