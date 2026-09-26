package com.local.comicreader;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
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
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public final class BrowserActivity extends Activity {
    private static final String START_URL = "https://comic18j-hbd.space/";
    private static final int FILE_CHOOSER_REQUEST = 3101;

    private WebView webView;
    private ProgressBar progressBar;
    private TextView titleView;
    private ValueCallback<Uri[]> filePathCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        AppSettings settings = new AppSettings(this);
        boolean dark = ThemeUtil.isDark(
                this,
                settings.getString("theme", "system")
        );
        ThemeUtil.applyWindow(this, dark);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(ThemeUtil.background(dark));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(8), dp(6), dp(8), dp(6));
        toolbar.setBackgroundColor(ThemeUtil.accentSoft(dark));

        Button back = toolbarButton("返回");
        back.setOnClickListener(view -> navigateBack());
        toolbar.addView(back);

        Button home = toolbarButton("首页");
        home.setOnClickListener(view -> webView.loadUrl(START_URL));
        toolbar.addView(home);

        Button refresh = toolbarButton("刷新");
        refresh.setOnClickListener(view -> webView.reload());
        toolbar.addView(refresh);

        titleView = new TextView(this);
        titleView.setText("浏览漫画");
        titleView.setTextSize(15);
        titleView.setTextColor(ThemeUtil.text(dark));
        titleView.setSingleLine(true);
        titleView.setGravity(Gravity.CENTER_VERTICAL);
        titleView.setPadding(dp(8), 0, dp(8), 0);
        toolbar.addView(titleView, new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.MATCH_PARENT,
                1
        ));
        root.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(54)
        ));

        progressBar = new ProgressBar(
                this,
                null,
                android.R.attr.progressBarStyleHorizontal
        );
        progressBar.setMax(100);
        root.addView(progressBar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(3)
        ));

        FrameLayout container = new FrameLayout(this);
        container.setBackgroundColor(ThemeUtil.surface(dark));
        webView = new WebView(this);
        webView.setBackgroundColor(ThemeUtil.surface(dark));
        container.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        root.addView(container, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));
        setContentView(root);
        configureWebView();

        if (savedInstanceState == null) {
            webView.loadUrl(START_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private Button toolbarButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setMinWidth(dp(60));
        return button;
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
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
        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view,
                    WebResourceRequest request
            ) {
                return openExternal(request.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                titleView.setText(view.getTitle());
                CookieManager.getInstance().flush();
            }

            @Override
            public void onReceivedError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceError error
            ) {
                if (request.isForMainFrame()) {
                    progressBar.setVisibility(View.GONE);
                    Toast.makeText(
                            BrowserActivity.this,
                            "网页加载失败，请检查网络或 VPN。",
                            Toast.LENGTH_LONG
                    ).show();
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int progress) {
                progressBar.setProgress(progress);
                progressBar.setVisibility(
                        progress >= 100 ? View.GONE : View.VISIBLE
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
                    FileChooserParams params
            ) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                try {
                    startActivityForResult(
                            Intent.createChooser(intent, "选择文件"),
                            FILE_CHOOSER_REQUEST
                    );
                    return true;
                } catch (RuntimeException error) {
                    filePathCallback = null;
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
                enqueueBrowserDownload(
                        url,
                        userAgent,
                        contentDisposition,
                        mimeType
                );
            }
        });
    }

    private boolean openExternal(Uri uri) {
        String scheme = uri.getScheme();
        if ("http".equalsIgnoreCase(scheme)
                || "https".equalsIgnoreCase(scheme)) {
            return false;
        }
        try {
            Intent intent;
            if ("intent".equalsIgnoreCase(scheme)) {
                intent = Intent.parseUri(
                        uri.toString(),
                        Intent.URI_INTENT_SCHEME
                );
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

    private void enqueueBrowserDownload(
            String url,
            String userAgent,
            String contentDisposition,
            String mimeType
    ) {
        if (url == null || !url.startsWith("http")) {
            Toast.makeText(
                    this,
                    "网页下载链接无效。",
                    Toast.LENGTH_SHORT
            ).show();
            return;
        }
        String fileName = URLUtil.guessFileName(
                url,
                contentDisposition,
                mimeType
        ).replaceAll("[\\\\/:*?\"<>|]", "_");
        DownloadManager.Request request = new DownloadManager.Request(
                Uri.parse(url)
        );
        request.setTitle(fileName);
        request.setDescription("JMComic 浏览页下载");
        request.setMimeType(mimeType);
        request.setAllowedOverMetered(true);
        request.setAllowedOverRoaming(false);
        request.setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
        );
        request.setDestinationInExternalFilesDir(
                this,
                Environment.DIRECTORY_DOWNLOADS,
                "JMComic/browser/" + fileName
        );
        String cookie = CookieManager.getInstance().getCookie(url);
        if (cookie != null && !cookie.isEmpty()) {
            request.addRequestHeader("Cookie", cookie);
        }
        if (userAgent != null && !userAgent.isEmpty()) {
            request.addRequestHeader("User-Agent", userAgent);
        }
        if (webView.getUrl() != null) {
            request.addRequestHeader("Referer", webView.getUrl());
        }
        DownloadManager manager = (DownloadManager) getSystemService(
                DOWNLOAD_SERVICE
        );
        manager.enqueue(request);
        Toast.makeText(
                this,
                "已加入系统下载队列。",
                Toast.LENGTH_SHORT
        ).show();
    }

    private void navigateBack() {
        if (webView != null && webView.canGoBack()) {
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
    protected void onSaveInstanceState(Bundle outState) {
        if (webView != null) {
            webView.saveState(outState);
        }
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
}
