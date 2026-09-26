package com.local.comicreader;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.format.Formatter;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class DownloadsActivity extends Activity {
    private static final String DESCRIPTION = "漫画助手下载";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final List<DownloadItem> items = new ArrayList<>();
    private DownloadAdapter adapter;
    private TextView emptyView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        setContentView(createContentView());
        loadDownloads();
    }

    private void configureWindow() {
        getWindow().setStatusBarColor(Color.rgb(15, 89, 100));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getWindow().setNavigationBarColor(Color.WHITE);
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            );
        }
    }

    private View createContentView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(4), 0, dp(4), 0);
        toolbar.setBackgroundColor(Color.rgb(15, 89, 100));
        toolbar.setElevation(dp(6));

        ImageButton backButton = new ImageButton(this);
        backButton.setImageResource(R.drawable.ic_arrow_back);
        backButton.setColorFilter(Color.WHITE);
        backButton.setContentDescription("返回");
        backButton.setBackgroundResource(
                android.R.drawable.list_selector_background
        );
        backButton.setPadding(dp(12), dp(12), dp(12), dp(12));
        backButton.setOnClickListener(view -> finish());
        toolbar.addView(backButton);

        TextView title = new TextView(this);
        title.setText("下载记录");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setPadding(dp(8), 0, dp(8), 0);
        toolbar.addView(
                title,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        1
                )
        );

        ImageButton refreshButton = new ImageButton(this);
        refreshButton.setImageResource(R.drawable.ic_refresh);
        refreshButton.setColorFilter(Color.WHITE);
        refreshButton.setContentDescription("刷新列表");
        refreshButton.setBackgroundResource(
                android.R.drawable.list_selector_background
        );
        refreshButton.setPadding(dp(12), dp(12), dp(12), dp(12));
        refreshButton.setOnClickListener(view -> loadDownloads());
        toolbar.addView(refreshButton);

        root.addView(
                toolbar,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        dp(56)
                )
        );

        ListView listView = new ListView(this);
        listView.setDividerHeight(1);
        listView.setDivider(new ColorDrawable(Color.rgb(222, 226, 229)));
        adapter = new DownloadAdapter();
        listView.setAdapter(adapter);

        emptyView = new TextView(this);
        emptyView.setText("暂无下载记录");
        emptyView.setTextColor(Color.rgb(95, 105, 110));
        emptyView.setTextSize(17);
        emptyView.setGravity(Gravity.CENTER);

        LinearLayout listContainer = new LinearLayout(this);
        listContainer.setOrientation(LinearLayout.VERTICAL);
        listContainer.addView(
                listView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );
        listContainer.addView(
                emptyView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );
        root.addView(
                listContainer,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );

        adapter.setListView(listView);
        listView.setOnItemClickListener((parent, view, position, id) ->
                openItem(items.get(position))
        );
        return root;
    }

    private void loadDownloads() {
        executor.execute(() -> {
            List<DownloadItem> loaded = queryDownloads();
            runOnUiThread(() -> {
                items.clear();
                items.addAll(loaded);
                adapter.notifyDataSetChanged();
                emptyView.setVisibility(
                        items.isEmpty() ? View.VISIBLE : View.GONE
                );
                adapter.getListView().setVisibility(
                        items.isEmpty() ? View.GONE : View.VISIBLE
                );
            });
        });
    }

    private List<DownloadItem> queryDownloads() {
        List<DownloadItem> result = new ArrayList<>();
        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        DownloadManager.Query query = new DownloadManager.Query();
        query.setFilterByStatus(
                DownloadManager.STATUS_PENDING
                        | DownloadManager.STATUS_RUNNING
                        | DownloadManager.STATUS_PAUSED
                        | DownloadManager.STATUS_SUCCESSFUL
                        | DownloadManager.STATUS_FAILED
        );
        try (Cursor cursor = manager.query(query)) {
            if (cursor == null) {
                return result;
            }
            int idColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_ID
            );
            int titleColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_TITLE
            );
            int statusColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_STATUS
            );
            int bytesColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR
            );
            int totalColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_TOTAL_SIZE_BYTES
            );
            int descriptionColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_DESCRIPTION
            );
            int mimeColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_MEDIA_TYPE
            );

            while (cursor.moveToNext()) {
                String description = cursor.getString(descriptionColumn);
                if (!DESCRIPTION.equals(description)) {
                    continue;
                }
                result.add(
                        new DownloadItem(
                                cursor.getLong(idColumn),
                                cursor.getString(titleColumn),
                                cursor.getInt(statusColumn),
                                cursor.getLong(bytesColumn),
                                cursor.getLong(totalColumn),
                                cursor.getString(mimeColumn)
                        )
                );
            }
        }
        result.sort((left, right) -> Long.compare(right.id, left.id));
        return result;
    }

    private void openItem(DownloadItem item) {
        if (item.status != DownloadManager.STATUS_SUCCESSFUL) {
            Toast.makeText(
                    this,
                    "文件尚未下载完成",
                    Toast.LENGTH_SHORT
            ).show();
            return;
        }

        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        Uri uri = manager.getUriForDownloadedFile(item.id);
        if (uri == null) {
            Toast.makeText(
                    this,
                    "找不到已下载文件",
                    Toast.LENGTH_SHORT
            ).show();
            return;
        }

        if (item.mimeType != null && item.mimeType.startsWith("image/")) {
            startActivity(
                    new Intent(this, ReaderActivity.class)
                            .putExtra(ReaderActivity.EXTRA_DOWNLOAD_ID, item.id)
            );
            return;
        }

        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, item.mimeType)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException error) {
            Toast.makeText(
                    this,
                    "没有可打开该文件的应用",
                    Toast.LENGTH_LONG
            ).show();
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(
                value * getResources().getDisplayMetrics().density
        );
    }

    private static String statusText(DownloadItem item) {
        switch (item.status) {
            case DownloadManager.STATUS_PENDING:
                return "等待下载";
            case DownloadManager.STATUS_RUNNING:
                if (item.totalBytes > 0) {
                    int percent = (int) (
                            item.bytesDownloaded * 100 / item.totalBytes
                    );
                    return "下载中 " + percent + "%";
                }
                return "下载中";
            case DownloadManager.STATUS_PAUSED:
                return "已暂停";
            case DownloadManager.STATUS_SUCCESSFUL:
                return "已完成";
            case DownloadManager.STATUS_FAILED:
                return "下载失败";
            default:
                return "未知状态";
        }
    }

    private final class DownloadAdapter extends BaseAdapter {
        private ListView listView;

        void setListView(ListView listView) {
            this.listView = listView;
        }

        ListView getListView() {
            return listView;
        }

        @Override
        public int getCount() {
            return items.size();
        }

        @Override
        public Object getItem(int position) {
            return items.get(position);
        }

        @Override
        public long getItemId(int position) {
            return items.get(position).id;
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
                row.setBackgroundColor(Color.WHITE);

                title = new TextView(DownloadsActivity.this);
                title.setTextColor(Color.rgb(32, 44, 48));
                title.setTextSize(16);
                title.setMaxLines(2);
                row.addView(title);

                details = new TextView(DownloadsActivity.this);
                details.setTextColor(Color.rgb(95, 105, 110));
                details.setTextSize(13);
                details.setPadding(0, dp(4), 0, 0);
                row.addView(details);
            }

            DownloadItem item = items.get(position);
            title.setText(item.title);
            String size = item.totalBytes > 0
                    ? Formatter.formatFileSize(
                            DownloadsActivity.this,
                            item.totalBytes
                    )
                    : "大小未知";
            details.setText(statusText(item) + " · " + size);
            return row;
        }
    }

    private static final class DownloadItem {
        final long id;
        final String title;
        final int status;
        final long bytesDownloaded;
        final long totalBytes;
        final String mimeType;

        DownloadItem(
                long id,
                String title,
                int status,
                long bytesDownloaded,
                long totalBytes,
                String mimeType
        ) {
            this.id = id;
            this.title = title == null ? "未命名文件" : title;
            this.status = status;
            this.bytesDownloaded = bytesDownloaded;
            this.totalBytes = totalBytes;
            this.mimeType = mimeType;
        }
    }
}
