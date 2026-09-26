package com.local.comicreader;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.util.Locale;

public final class MainActivity extends Activity {
    private static final String START_URL = "https://comic18j-hbd.space/";
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int STORAGE_PERMISSION_REQUEST = 1002;

    private WebView webView;
    private ProgressBar pageProgress;
    private ImageButton backButton;
    private ValueCallback<Uri[]> filePathCallback;
    private PendingDownload pendingDownload;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureWindow();
        configureCookies();
        setContentView(createContentView());
        configureWebView();

        if (savedInstanceState == null) {
            webView.loadUrl(START_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
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

    private void configureCookies() {
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
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

        backButton = createToolbarButton(
                R.drawable.ic_arrow_back,
                "返回上一页"
        );
        backButton.setAlpha(0.45f);
        backButton.setOnClickListener(view -> navigateBack());
        toolbar.addView(backButton);

        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setPadding(dp(8), 0, dp(8), 0);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.MATCH_PARENT,
                1
        );
        toolbar.addView(title, titleParams);

        ImageButton refreshButton = createToolbarButton(
                R.drawable.ic_refresh,
                "刷新"
        );
        refreshButton.setOnClickListener(view -> webView.reload());
        toolbar.addView(refreshButton);

        ImageButton downloadsButton = createToolbarButton(
                R.drawable.ic_download,
                "下载记录"
        );
        downloadsButton.setOnClickListener(view ->
                startActivity(new Intent(this, DownloadsActivity.class))
        );
        toolbar.addView(downloadsButton);

        root.addView(
                toolbar,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        dp(56)
                )
        );

        pageProgress = new ProgressBar(
                this,
                null,
                android.R.attr.progressBarStyleHorizontal
        );
        pageProgress.setMax(100);
        pageProgress.setProgress(0);
        pageProgress.setVisibility(View.GONE);
        root.addView(
                pageProgress,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        dp(3)
                )
        );

        FrameLayout webContainer = new FrameLayout(this);
        webContainer.setBackgroundColor(Color.WHITE);
        webView = new WebView(this);
        webContainer.addView(
                webView,
                new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT
                )
        );
        root.addView(
                webContainer,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );

        return root;
    }

    private ImageButton createToolbarButton(int drawable, String description) {
        ImageButton button = new ImageButton(this);
        button.setImageResource(drawable);
        button.setColorFilter(Color.WHITE);
        button.setContentDescription(description);
        button.setBackgroundResource(
                android.R.drawable.list_selector_background
        );
        button.setPadding(dp(12), dp(12), dp(12), dp(12));
        return button;
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setLoadsImagesAutomatically(true);
        settings.setBlockNetworkLoads(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setMixedContentMode(
                WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        );

        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        WebView.setWebContentsDebuggingEnabled(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view,
                    WebResourceRequest request
            ) {
                return openSupportedUri(request.getUrl());
            }

            @Override
            public void onPageStarted(
                    WebView view,
                    String url,
                    android.graphics.Bitmap favicon
            ) {
                pageProgress.setVisibility(View.VISIBLE);
                pageProgress.setProgress(0);
                updateBackButton();
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageProgress.setVisibility(View.GONE);
                updateBackButton();
                CookieManager.getInstance().flush();
            }

            @Override
            public void onReceivedError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    pageProgress.setVisibility(View.GONE);
                    showLoadError();
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                pageProgress.setProgress(newProgress);
                pageProgress.setVisibility(
                        newProgress >= 100 ? View.GONE : View.VISIBLE
                );
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                request.deny();
            }

            @Override
            public boolean onShowFileChooser(
                    WebView webView,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams fileChooserParams
            ) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;

                Intent chooser = new Intent(Intent.ACTION_GET_CONTENT);
                chooser.addCategory(Intent.CATEGORY_OPENABLE);
                chooser.setType(resolveChooserType(fileChooserParams));
                if (fileChooserParams.getMode()
                        == FileChooserParams.MODE_OPEN_MULTIPLE) {
                    chooser.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                }

                try {
                    startActivityForResult(
                            Intent.createChooser(chooser, "选择文件"),
                            FILE_CHOOSER_REQUEST
                    );
                    return true;
                } catch (RuntimeException error) {
                    filePathCallback = null;
                    Toast.makeText(
                            MainActivity.this,
                            "无法打开文件选择器",
                            Toast.LENGTH_SHORT
                    ).show();
                    return false;
                }
            }
        });

        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(
                    String url,
                    String userAgent,
                    String contentDisposition,
                    String mimeType,
                    long contentLength
            ) {
                requestDownload(
                        url,
                        userAgent,
                        contentDisposition,
                        mimeType
                );
            }
        });
    }

    private String resolveChooserType(WebChromeClient.FileChooserParams params) {
        String[] acceptedTypes = params.getAcceptTypes();
        if (acceptedTypes == null || acceptedTypes.length == 0) {
            return "*/*";
        }
        for (String acceptedType : acceptedTypes) {
            if (acceptedType != null && acceptedType.length() > 0) {
                return acceptedType;
            }
        }
        return acceptedTypes[0];
    }

    private boolean openSupportedUri(Uri uri) {
        String scheme = uri.getScheme();
        if ("http".equalsIgnoreCase(scheme)
                || "https".equalsIgnoreCase(scheme)) {
            return false;
        }

        try {
            Intent intent;
            if ("intent".equalsIgnoreCase(scheme)) {
                intent = Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME);
            } else {
                intent = new Intent(Intent.ACTION_VIEW, uri);
            }
            startActivity(intent);
        } catch (Exception error) {
            Toast.makeText(
                    this,
                    "没有可处理该链接的应用",
                    Toast.LENGTH_SHORT
            ).show();
        }
        return true;
    }

    private void requestDownload(
            String url,
            String userAgent,
            String contentDisposition,
            String mimeType
    ) {
        if (url == null || !(url.startsWith("http://")
                || url.startsWith("https://"))) {
            Toast.makeText(
                    this,
                    "该下载需要网站自身完成，请在原页面操作",
                    Toast.LENGTH_LONG
            ).show();
            return;
        }

        PendingDownload download = new PendingDownload(
                url,
                userAgent,
                contentDisposition,
                mimeType
        );
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
            pendingDownload = download;
            requestPermissions(
                    new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE},
                    STORAGE_PERMISSION_REQUEST
            );
            return;
        }

        enqueueDownload(download);
    }

    private void enqueueDownload(PendingDownload download) {
        String fileName = URLUtil.guessFileName(
                download.url,
                download.contentDisposition,
                download.mimeType
        );
        fileName = sanitizeFileName(fileName);
        if (fileName.length() == 0) {
            fileName = "download_" + System.currentTimeMillis();
        }

        DownloadManager.Request request = new DownloadManager.Request(
                Uri.parse(download.url)
        );
        request.setTitle(fileName);
        request.setDescription("漫画助手下载");
        request.setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
        );
        request.setAllowedOverMetered(true);
        request.setAllowedOverRoaming(false);
        request.allowScanningByMediaScanner();
        request.setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS,
                "ComicReader/" + fileName
        );

        if (download.mimeType != null && download.mimeType.length() > 0) {
            request.setMimeType(download.mimeType);
        }
        String cookie = CookieManager.getInstance().getCookie(download.url);
        if (cookie != null && cookie.length() > 0) {
            request.addRequestHeader("Cookie", cookie);
        }
        if (download.userAgent != null && download.userAgent.length() > 0) {
            request.addRequestHeader("User-Agent", download.userAgent);
        }
        String referer = webView.getUrl();
        if (referer != null) {
            request.addRequestHeader("Referer", referer);
        }

        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        manager.enqueue(request);
        Toast.makeText(
                this,
                "已加入系统下载队列",
                Toast.LENGTH_SHORT
        ).show();
    }

    private String sanitizeFileName(String fileName) {
        String sanitized = fileName == null ? "" : fileName;
        sanitized = sanitized.replaceAll("[\\\\/:*?\"<>|]", "_");
        sanitized = sanitized.replaceAll("\\s+", " ").trim();
        while (sanitized.startsWith(".")) {
            sanitized = sanitized.substring(1);
        }
        return sanitized;
    }

    private void showLoadError() {
        String html = "<!doctype html><html><head><meta name=\"viewport\" "
                + "content=\"width=device-width,initial-scale=1\"></head>"
                + "<body style=\"font-family:sans-serif;padding:32px;color:#233;"
                + "background:#fff\"><h2>页面暂时无法打开</h2>"
                + "<p>请检查网络连接，然后点击顶部刷新按钮重试。</p>"
                + "</body></html>";
        webView.loadDataWithBaseURL(
                null,
                html,
                "text/html",
                "UTF-8",
                null
        );
    }

    private void updateBackButton() {
        if (backButton == null || webView == null) {
            return;
        }
        boolean canGoBack = webView.canGoBack();
        backButton.setEnabled(canGoBack);
        backButton.setAlpha(canGoBack ? 1.0f : 0.45f);
    }

    private void navigateBack() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            finish();
        }
    }

    @Override
    public void onBackPressed() {
        navigateBack();
    }

    @Override
    protected void onActivityResult(
            int requestCode,
            int resultCode,
            Intent data
    ) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }

        Uri[] result = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                result = new Uri[count];
                for (int index = 0; index < count; index++) {
                    result[index] = data.getClipData()
                            .getItemAt(index)
                            .getUri();
                }
            } else if (data.getData() != null) {
                result = new Uri[]{data.getData()};
            }
        }

        filePathCallback.onReceiveValue(result);
        filePathCallback = null;
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults
    ) {
        super.onRequestPermissionsResult(
                requestCode,
                permissions,
                grantResults
        );
        if (requestCode != STORAGE_PERMISSION_REQUEST
                || pendingDownload == null) {
            return;
        }

        PendingDownload download = pendingDownload;
        pendingDownload = null;
        if (grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            enqueueDownload(download);
            return;
        }

        Toast.makeText(
                this,
                "未获得存储权限，无法保存下载文件",
                Toast.LENGTH_LONG
        ).show();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onPause() {
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(
                value * getResources().getDisplayMetrics().density
        );
    }

    private static final class PendingDownload {
        final String url;
        final String userAgent;
        final String contentDisposition;
        final String mimeType;

        PendingDownload(
                String url,
                String userAgent,
                String contentDisposition,
                String mimeType
        ) {
            this.url = url;
            this.userAgent = userAgent;
            this.contentDisposition = contentDisposition;
            this.mimeType = mimeType;
        }
    }
}
