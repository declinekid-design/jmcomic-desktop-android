package com.local.comicreader;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.ContentResolver;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.drawable.BitmapDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ReaderActivity extends Activity {
    public static final String EXTRA_DOWNLOAD_ID = "download_id";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final List<Long> imageIds = new ArrayList<>();
    private ImageView imageView;
    private TextView titleView;
    private Button previousButton;
    private Button nextButton;
    private int currentIndex = -1;
    private int decodeGeneration;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        configureWindow();
        setContentView(createContentView());

        long currentId = getIntent().getLongExtra(EXTRA_DOWNLOAD_ID, -1L);
        if (currentId < 0) {
            finish();
            return;
        }
        loadImageIds(currentId);
    }

    private void configureWindow() {
        getWindow().setStatusBarColor(Color.rgb(24, 29, 31));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getWindow().setNavigationBarColor(Color.rgb(24, 29, 31));
        }
    }

    private View createContentView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(24, 29, 31));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(4), 0, dp(4), 0);
        toolbar.setBackgroundColor(Color.rgb(24, 29, 31));

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

        titleView = new TextView(this);
        titleView.setTextColor(Color.WHITE);
        titleView.setTextSize(15);
        titleView.setGravity(Gravity.CENTER);
        titleView.setMaxLines(2);
        toolbar.addView(
                titleView,
                new LinearLayout.LayoutParams(
                        0,
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        1
                )
        );

        Button previousTop = createNavButton("上一页");
        previousTop.setOnClickListener(view -> showPrevious());
        toolbar.addView(previousTop);

        Button nextTop = createNavButton("下一页");
        nextTop.setOnClickListener(view -> showNext());
        toolbar.addView(nextTop);

        root.addView(
                toolbar,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        dp(56)
                )
        );

        FrameLayout imageContainer = new FrameLayout(this);
        imageContainer.setBackgroundColor(Color.rgb(8, 11, 12));
        imageView = new ImageView(this);
        imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imageView.setAdjustViewBounds(false);
        imageContainer.addView(
                imageView,
                new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT
                )
        );
        root.addView(
                imageContainer,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );

        LinearLayout navigation = new LinearLayout(this);
        navigation.setOrientation(LinearLayout.HORIZONTAL);
        navigation.setGravity(Gravity.CENTER);
        navigation.setPadding(dp(12), dp(8), dp(12), dp(8));
        navigation.setBackgroundColor(Color.rgb(24, 29, 31));

        previousButton = createNavButton("上一页");
        previousButton.setOnClickListener(view -> showPrevious());
        navigation.addView(previousButton);

        nextButton = createNavButton("下一页");
        nextButton.setOnClickListener(view -> showNext());
        navigation.addView(nextButton);

        root.addView(
                navigation,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                )
        );
        return root;
    }

    private Button createNavButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextColor(Color.WHITE);
        button.setTextSize(14);
        button.setMinWidth(dp(76));
        button.setBackgroundResource(
                android.R.drawable.list_selector_background
        );
        return button;
    }

    private void loadImageIds(long currentId) {
        executor.execute(() -> {
            List<Long> loaded = queryImageIds();
            int index = loaded.indexOf(currentId);
            if (index < 0) {
                loaded.add(currentId);
                index = loaded.size() - 1;
            }
            int finalIndex = index;
            runOnUiThread(() -> {
                imageIds.clear();
                imageIds.addAll(loaded);
                currentIndex = finalIndex;
                showCurrent();
            });
        });
    }

    private List<Long> queryImageIds() {
        List<Long> result = new ArrayList<>();
        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        DownloadManager.Query query = new DownloadManager.Query();
        query.setFilterByStatus(DownloadManager.STATUS_SUCCESSFUL);

        try (Cursor cursor = manager.query(query)) {
            if (cursor == null) {
                return result;
            }
            int idColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_ID
            );
            int mimeColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_MEDIA_TYPE
            );
            int descriptionColumn = cursor.getColumnIndexOrThrow(
                    DownloadManager.COLUMN_DESCRIPTION
            );

            while (cursor.moveToNext()) {
                String description = cursor.getString(descriptionColumn);
                String mime = cursor.getString(mimeColumn);
                if ("漫画助手下载".equals(description)
                        && mime != null
                        && mime.startsWith("image/")) {
                    result.add(cursor.getLong(idColumn));
                }
            }
        }
        result.sort(Long::compare);
        return result;
    }

    private void showCurrent() {
        if (currentIndex < 0 || currentIndex >= imageIds.size()) {
            Toast.makeText(
                    this,
                    "找不到可阅读的图片",
                    Toast.LENGTH_SHORT
            ).show();
            finish();
            return;
        }

        long downloadId = imageIds.get(currentIndex);
        previousButton.setEnabled(currentIndex > 0);
        nextButton.setEnabled(currentIndex < imageIds.size() - 1);
        previousButton.setAlpha(previousButton.isEnabled() ? 1.0f : 0.4f);
        nextButton.setAlpha(nextButton.isEnabled() ? 1.0f : 0.4f);
        titleView.setText(
                (currentIndex + 1) + " / " + imageIds.size()
                        + "  ·  正在加载"
        );

        int generation = ++decodeGeneration;
        executor.execute(() -> {
            Bitmap bitmap = decodeBitmap(downloadId);
            runOnUiThread(() -> {
                if (generation != decodeGeneration || isFinishing()) {
                    if (bitmap != null) {
                        bitmap.recycle();
                    }
                    return;
                }
                if (bitmap == null) {
                    imageView.setImageDrawable(null);
                    titleView.setText("图片加载失败");
                    return;
                }
                Bitmap previous = null;
                if (imageView.getDrawable() instanceof BitmapDrawable) {
                    previous = ((BitmapDrawable) imageView.getDrawable())
                            .getBitmap();
                }
                imageView.setImageBitmap(bitmap);
                if (previous != null && previous != bitmap) {
                    previous.recycle();
                }
                titleView.setText(
                        (currentIndex + 1) + " / " + imageIds.size()
                );
            });
        });
    }

    private Bitmap decodeBitmap(long downloadId) {
        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        Uri uri = manager.getUriForDownloadedFile(downloadId);
        if (uri == null) {
            return null;
        }

        ContentResolver resolver = getContentResolver();
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream stream = resolver.openInputStream(uri)) {
            BitmapFactory.decodeStream(stream, null, bounds);
        } catch (Exception ignored) {
            return null;
        }

        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = calculateSampleSize(
                bounds.outWidth,
                bounds.outHeight
        );
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        try (InputStream stream = resolver.openInputStream(uri)) {
            return BitmapFactory.decodeStream(stream, null, options);
        } catch (Exception ignored) {
            return null;
        }
    }

    private int calculateSampleSize(int width, int height) {
        int targetWidth = getResources().getDisplayMetrics().widthPixels;
        int targetHeight = getResources().getDisplayMetrics().heightPixels;
        int sample = 1;
        while (width / (sample * 2) >= targetWidth
                && height / (sample * 2) >= targetHeight) {
            sample *= 2;
        }
        return sample;
    }

    private void showPrevious() {
        if (currentIndex > 0) {
            currentIndex--;
            showCurrent();
        }
    }

    private void showNext() {
        if (currentIndex < imageIds.size() - 1) {
            currentIndex++;
            showCurrent();
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
}
