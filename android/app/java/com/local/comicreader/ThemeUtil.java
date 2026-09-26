package com.local.comicreader;

import android.app.Activity;
import android.content.res.Configuration;
import android.graphics.Color;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.view.WindowInsetsController;

final class ThemeUtil {
    static final int LIGHT_BACKGROUND = Color.rgb(246, 248, 249);
    static final int LIGHT_SURFACE = Color.WHITE;
    static final int LIGHT_TEXT = Color.rgb(28, 38, 42);
    static final int LIGHT_MUTED = Color.rgb(87, 102, 108);
    static final int LIGHT_BORDER = Color.rgb(216, 223, 226);
    static final int LIGHT_ACCENT = Color.rgb(13, 111, 112);
    static final int LIGHT_ACCENT_SOFT = Color.rgb(220, 241, 239);

    static final int DARK_BACKGROUND = Color.rgb(16, 21, 23);
    static final int DARK_SURFACE = Color.rgb(26, 33, 36);
    static final int DARK_TEXT = Color.rgb(239, 245, 246);
    static final int DARK_MUTED = Color.rgb(170, 184, 189);
    static final int DARK_BORDER = Color.rgb(58, 70, 74);
    static final int DARK_ACCENT = Color.rgb(77, 205, 196);
    static final int DARK_ACCENT_SOFT = Color.rgb(22, 63, 63);

    private ThemeUtil() {
    }

    static boolean isDark(Activity activity, String preference) {
        if ("dark".equals(preference)) {
            return true;
        }
        if ("light".equals(preference)) {
            return false;
        }
        int mode = activity.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK;
        return mode == Configuration.UI_MODE_NIGHT_YES;
    }

    static int background(boolean dark) {
        return dark ? DARK_BACKGROUND : LIGHT_BACKGROUND;
    }

    static int surface(boolean dark) {
        return dark ? DARK_SURFACE : LIGHT_SURFACE;
    }

    static int text(boolean dark) {
        return dark ? DARK_TEXT : LIGHT_TEXT;
    }

    static int muted(boolean dark) {
        return dark ? DARK_MUTED : LIGHT_MUTED;
    }

    static int border(boolean dark) {
        return dark ? DARK_BORDER : LIGHT_BORDER;
    }

    static int accent(boolean dark) {
        return dark ? DARK_ACCENT : LIGHT_ACCENT;
    }

    static int accentSoft(boolean dark) {
        return dark ? DARK_ACCENT_SOFT : LIGHT_ACCENT_SOFT;
    }

    static void applyWindow(Activity activity, boolean dark) {
        Window window = activity.getWindow();
        int color = dark ? DARK_BACKGROUND : LIGHT_ACCENT;
        window.setStatusBarColor(color);
        window.setNavigationBarColor(dark ? DARK_BACKGROUND : LIGHT_SURFACE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {
                controller.setSystemBarsAppearance(
                        dark ? 0 : WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS,
                        WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                                | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
                );
                controller.setSystemBarsAppearance(
                        dark ? 0 : WindowInsetsController
                                .APPEARANCE_LIGHT_NAVIGATION_BARS,
                        WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
                );
            }
            return;
        }
        int flags = View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        if (!dark) {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        }
        window.getDecorView().setSystemUiVisibility(flags);
    }
}
