package com.local.comicreader;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.format.Formatter;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class DownloadsActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<File> files = new ArrayList<>();
    private AppSettings settings;
    private boolean dark;
    private FileAdapter adapter;
    private TextView emptyView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        settings = new AppSettings(this);
        dark = ThemeUtil.isDark(
                this,
                settings.getString("theme", "system")
        );
        setContentView(createUi());
        ThemeUtil.applyWindow(this, dark);
        loadFiles();
    }

    private View createUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(ThemeUtil.background(dark));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(8), dp(6), dp(8), dp(6));
        toolbar.setBackgroundColor(ThemeUtil.accentSoft(dark));

        Button back = button("返回");
        back.setOnClickListener(view -> finish());
        toolbar.addView(back);

        TextView title = new TextView(this);
        title.setText("下载结果");
        title.setTextSize(18);
        title.setTextColor(ThemeUtil.text(dark));
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setPadding(dp(8), 0, dp(8), 0);
        toolbar.addView(title, new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.MATCH_PARENT,
                1
        ));

        Button refresh = button("刷新");
        refresh.setOnClickListener(view -> loadFiles());
        toolbar.addView(refresh);
        root.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(54)
        ));

        TextView location = new TextView(this);
        location.setText(settings.downloadDir().getAbsolutePath());
        location.setTextSize(12);
        location.setTextColor(ThemeUtil.muted(dark));
        location.setTextIsSelectable(true);
        location.setPadding(dp(14), dp(8), dp(14), dp(4));
        root.addView(location);

        ListView listView = new ListView(this);
        listView.setDividerHeight(0);
        adapter = new FileAdapter();
        listView.setAdapter(adapter);
        listView.setOnItemClickListener((parent, view, position, id) ->
                openFile(files.get(position))
        );
        root.addView(listView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));

        emptyView = new TextView(this);
        emptyView.setText("暂无 ZIP 或图片结果。\n下载完成后回到本页刷新。");
        emptyView.setTextSize(15);
        emptyView.setTextColor(ThemeUtil.muted(dark));
        emptyView.setGravity(Gravity.CENTER);
        root.addView(emptyView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));
        return root;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(13);
        return button;
    }

    private void loadFiles() {
        executor.execute(() -> {
            List<File> found = new ArrayList<>();
            collect(settings.downloadDir(), found, 0);
            found.sort((left, right) ->
                    Long.compare(right.lastModified(), left.lastModified())
            );
            handler.post(() -> {
                files.clear();
                files.addAll(found);
                adapter.notifyDataSetChanged();
                emptyView.setVisibility(
                        files.isEmpty() ? View.VISIBLE : View.GONE
                );
            });
        });
    }

    private void collect(File directory, List<File> result, int depth) {
        if (directory == null || depth > 4) {
            return;
        }
        File[] children = directory.listFiles();
        if (children == null) {
            return;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                collect(child, result, depth + 1);
                continue;
            }
            String name = child.getName().toLowerCase(Locale.ROOT);
            if (name.endsWith(".zip")
                    || name.endsWith(".jpg")
                    || name.endsWith(".jpeg")
                    || name.endsWith(".png")
                    || name.endsWith(".webp")
                    || name.endsWith(".gif")
                    || name.endsWith(".apk")) {
                result.add(child);
                if (result.size() >= 500) {
                    return;
                }
            }
        }
    }

    private void openFile(File file) {
        String mime;
        String name = file.getName().toLowerCase(Locale.ROOT);
        if (name.endsWith(".zip")) {
            mime = "application/zip";
        } else if (name.endsWith(".apk")) {
            mime = "application/vnd.android.package-archive";
        } else {
            mime = "image/*";
        }
        Uri uri = FileProvider.getUriForFile(
                this,
                getPackageName() + ".files",
                file
        );
        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, mime)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException error) {
            Toast.makeText(
                    this,
                    "没有可打开该文件类型的应用。",
                    Toast.LENGTH_LONG
            ).show();
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(
                value * getResources().getDisplayMetrics().density
        );
    }

    private final class FileAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return files.size();
        }

        @Override
        public Object getItem(int position) {
            return files.get(position);
        }

        @Override
        public long getItemId(int position) {
            return files.get(position).lastModified();
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            LinearLayout row;
            TextView title;
            TextView details;
            if (convertView instanceof LinearLayout) {
                row = (LinearLayout) convertView;
                title = (TextView) row.getChildAt(0);
                details = (TextView) row.getChildAt(1);
            } else {
                row = new LinearLayout(DownloadsActivity.this);
                row.setOrientation(LinearLayout.VERTICAL);
                row.setPadding(dp(16), dp(12), dp(16), dp(12));
                row.setBackgroundColor(ThemeUtil.surface(dark));
                title = new TextView(DownloadsActivity.this);
                title.setTextSize(15);
                title.setTextColor(ThemeUtil.text(dark));
                title.setMaxLines(2);
                row.addView(title);
                details = new TextView(DownloadsActivity.this);
                details.setTextSize(12);
                details.setTextColor(ThemeUtil.muted(dark));
                details.setPadding(0, dp(4), 0, 0);
                details.setMaxLines(2);
                row.addView(details);
            }
            File file = files.get(position);
            title.setText(file.getName());
            String size = Formatter.formatFileSize(
                    DownloadsActivity.this,
                    file.length()
            );
            String date = DateFormat.getDateTimeInstance(
                    DateFormat.SHORT,
                    DateFormat.SHORT
            ).format(new Date(file.lastModified()));
            details.setText(date + " · " + size + "\n" + file.getParent());
            return row;
        }
    }
}
