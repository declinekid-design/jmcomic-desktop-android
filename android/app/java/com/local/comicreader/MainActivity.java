package com.local.comicreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String[] THEME_LABELS = {
            "跟随系统", "浅色主题", "深色主题"
    };
    private static final String[] THEME_VALUES = {
            "system", "light", "dark"
    };
    private static final String[] NAMING_LABELS = {
            "按车号命名", "按漫画名命名"
    };
    private static final String[] NAMING_VALUES = {
            "id", "title"
    };
    private static final String[] SUFFIX_LABELS = {
            "保持原格式", "JPG", "PNG", "WEBP"
    };
    private static final String[] SUFFIX_VALUES = {
            "", ".jpg", ".png", ".webp"
    };
    private static final String[] CLIENT_LABELS = {
            "APP 接口", "网页接口"
    };
    private static final String[] CLIENT_VALUES = {
            "api", "html"
    };
    private static final String[] PROXY_LABELS = {
            "跟随系统/VPN", "不使用代理", "手动输入"
    };
    private static final String[] PROXY_VALUES = {
            "system", "none", "manual"
    };

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final List<String> episodeIds = new ArrayList<>();

    private AppSettings settings;
    private PyObject python;
    private boolean dark;
    private boolean initialized;
    private boolean busy;
    private boolean downloadRunning;
    private boolean themeReady;
    private boolean updateCheckStarted;
    private JSONObject currentAlbum;

    private LinearLayout root;
    private LinearLayout content;
    private EditText queryInput;
    private EditText imageThreadsInput;
    private EditText chapterThreadsInput;
    private EditText proxyInput;
    private EditText manifestInput;
    private Spinner themeSpinner;
    private Spinner namingSpinner;
    private Spinner suffixSpinner;
    private Spinner clientSpinner;
    private Spinner proxySpinner;
    private Spinner chapterStartSpinner;
    private Spinner chapterEndSpinner;
    private CheckBox packZipCheck;
    private CheckBox deleteZipCheck;
    private CheckBox autoUpdateCheck;
    private TextView detailView;
    private TextView logView;
    private TextView statusView;
    private TextView progressView;
    private TextView folderView;
    private TextView loginStatusView;
    private TextView updateStatusView;
    private ProgressBar progressBar;
    private Button queryButton;
    private Button downloadButton;
    private Button cancelButton;
    private Button loginButton;
    private Button logoutButton;
    private Button updateButton;

    private final Runnable pollRunnable = new Runnable() {
        @Override
        public void run() {
            pollPythonEvents();
            handler.postDelayed(this, 450);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        StartupDiagnostics.record(this, "MainActivity.onCreate begin");
        settings = new AppSettings(this);
        dark = ThemeUtil.isDark(
                this,
                settings.getString("theme", "system")
        );
        setContentView(createUi());
        ThemeUtil.applyWindow(this, dark);
        styleTree(root);

        showPreviousCrashIfPresent();
        initializePython();
        StartupDiagnostics.record(this, "MainActivity.onCreate complete");
    }

    private void showPreviousCrashIfPresent() {
        String diagnostics = StartupDiagnostics.read(this);
        int fatalIndex = diagnostics.lastIndexOf("FATAL");
        if (fatalIndex < 0) {
            return;
        }
        String detail = diagnostics.substring(fatalIndex);
        statusView.setText("检测到上次启动闪退，错误信息已写入 startup.log。");
        appendLog(
                "上次启动异常：\n"
                        + detail.substring(0, Math.min(detail.length(), 4000))
        );
    }

    private View createUi() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(ThemeUtil.background(dark));

        root.addView(createHeader());

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(16), dp(12), dp(16), dp(28));
        scrollView.addView(
                content,
                new ScrollView.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                )
        );
        root.addView(
                scrollView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );

        addSection("作品查询");
        LinearLayout queryRow = horizontal();
        queryInput = editText(
                "例如 123456、JM123456、p123456 或禁漫链接",
                false
        );
        queryRow.addView(
                queryInput,
                new LinearLayout.LayoutParams(0, dp(52), 1)
        );
        queryButton = button("查询详情", ThemeUtil.accent(dark));
        queryButton.setOnClickListener(view -> queryAlbum());
        queryRow.addView(queryButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(52)
        ));
        content.addView(queryRow);
        addHint(
                "支持纯车号、JM 编号、章节号 p123456，以及 albums 或 photos "
                        + "页面链接。查询只读取详情，不会下载图片。"
        );

        chapterStartSpinner = spinner(new String[0]);
        chapterEndSpinner = spinner(new String[0]);
        chapterStartSpinner.setEnabled(false);
        chapterEndSpinner.setEnabled(false);
        chapterStartSpinner.setOnItemSelectedListener(
                new SimpleItemSelectedListener() {
                    @Override
                    public void onItemSelected(int position) {
                        if (position > chapterEndSpinner.getSelectedItemPosition()) {
                            chapterEndSpinner.setSelection(position);
                        }
                    }
                }
        );
        chapterEndSpinner.setOnItemSelectedListener(
                new SimpleItemSelectedListener() {
                    @Override
                    public void onItemSelected(int position) {
                        if (position < chapterStartSpinner.getSelectedItemPosition()) {
                            chapterStartSpinner.setSelection(position);
                        }
                    }
                }
        );
        LinearLayout chapterRow = horizontal();
        chapterRow.addView(
                chapterStartSpinner,
                new LinearLayout.LayoutParams(0, dp(50), 1)
        );
        TextView toLabel = label("到", 15, ThemeUtil.text(dark));
        toLabel.setGravity(Gravity.CENTER);
        chapterRow.addView(toLabel, new LinearLayout.LayoutParams(
                dp(42),
                dp(50)
        ));
        chapterRow.addView(
                chapterEndSpinner,
                new LinearLayout.LayoutParams(0, dp(50), 1)
        );
        Button allChapters = button("全部章节", ThemeUtil.accentSoft(dark));
        allChapters.setTextColor(ThemeUtil.accent(dark));
        allChapters.setOnClickListener(view -> selectAllChapters());
        chapterRow.addView(allChapters, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(50)
        ));
        content.addView(chapterRow);
        addHint("查询后可选择起始话和结束话，范围包含起始与结束章节。");

        detailView = label(
                "尚未查询作品详情。",
                14,
                ThemeUtil.text(dark)
        );
        detailView.setTypeface(Typeface.MONOSPACE);
        detailView.setTextIsSelectable(true);
        detailView.setPadding(dp(12), dp(12), dp(12), dp(12));
        detailView.setBackgroundColor(ThemeUtil.surface(dark));
        LinearLayout.LayoutParams detailParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(260)
        );
        detailParams.topMargin = dp(8);
        content.addView(detailView, detailParams);

        addSection("保存与命名");
        folderView = label(
                "程序下载目录：" + settings.downloadDir().getAbsolutePath(),
                13,
                ThemeUtil.muted(dark)
        );
        folderView.setTextIsSelectable(true);
        content.addView(folderView);
        addHint(
                "Android 将下载、会话、日志和更新文件都放在应用自身目录，"
                        + "不使用桌面 AppData；可通过“结果”打开或分享文件。"
        );

        namingSpinner = spinner(NAMING_LABELS);
        selectSpinnerValue(namingSpinner, NAMING_VALUES, settings.getString(
                "naming",
                "id"
        ));
        addSetting(
                "作品文件夹命名",
                namingSpinner,
                "按车号会生成 JM车号 文件夹或 ZIP；按漫画名使用作品标题。"
        );

        packZipCheck = checkBox(
                "多话作品打包为 ZIP",
                settings.getBoolean("pack_zip", true)
        );
        addSetting(
                "ZIP 打包",
                packZipCheck,
                "下载多话时生成一个 ZIP，ZIP 内按“第几话 话名”建立文件夹；"
                        + "只下载一话时不打包。"
        );
        deleteZipCheck = checkBox(
                "打包成功后删除中间图片文件夹",
                settings.getBoolean("delete_after_zip", true)
        );
        addSetting(
                "ZIP 清理",
                deleteZipCheck,
                "只在 ZIP 创建成功后删除本次产生的中间章节文件夹，"
                        + "不会处理其他已有文件。"
        );

        addSection("下载与网络");
        clientSpinner = spinner(CLIENT_LABELS);
        selectSpinnerValue(
                clientSpinner,
                CLIENT_VALUES,
                settings.getString("client", "api")
        );
        addSetting(
                "作品接口",
                clientSpinner,
                "APP 接口通常更稳定；网页接口可绕过部分接口限制，"
                        + "遇到失败时可在两者间切换。"
        );

        imageThreadsInput = editText("1 到 50", true);
        imageThreadsInput.setText(String.valueOf(
                settings.getInt("image_threads", 10)
        ));
        addSetting(
                "图片并发",
                imageThreadsInput,
                "同时下载的图片数，建议 8 到 16。数值越高速度可能越快，"
                        + "但会增加站点压力和失败概率。"
        );
        chapterThreadsInput = editText("1 到 64", true);
        chapterThreadsInput.setText(String.valueOf(
                settings.getInt("chapter_threads", 4)
        ));
        addSetting(
                "章节并发",
                chapterThreadsInput,
                "同时处理的话数，普通网络建议 4 到 8；长作品可适当提高。"
        );

        suffixSpinner = spinner(SUFFIX_LABELS);
        Object savedSuffix = settings.pythonConfig().opt("image_suffix");
        selectSpinnerValue(
                suffixSpinner,
                SUFFIX_VALUES,
                savedSuffix == null ? "" : String.valueOf(savedSuffix)
        );
        addSetting(
                "图片格式",
                suffixSpinner,
                "保持原格式不会二次转码；JPG、PNG、WEBP 会在下载后转换，"
                        + "耗时和存储占用略有变化。"
        );

        proxySpinner = spinner(PROXY_LABELS);
        selectSpinnerValue(
                proxySpinner,
                PROXY_VALUES,
                settings.getString("proxy_mode", "system")
        );
        addSetting(
                "代理方式",
                proxySpinner,
                "跟随系统/VPN 使用 Android 当前网络；不使用代理适合直连；"
                        + "手动输入适合本机或局域网代理。"
        );
        proxyInput = editText("例如 127.0.0.1:7890", false);
        proxyInput.setText(settings.getString("proxy", ""));
        addSetting(
                "手动代理地址",
                proxyInput,
                "仅在选择“手动输入”时生效，地址可包含或省略 http://。"
        );
        proxySpinner.setOnItemSelectedListener(new SimpleItemSelectedListener() {
            @Override
            public void onItemSelected(int position) {
                updateProxyInput();
            }
        });
        updateProxyInput();

        addSection("账号与更新");
        loginStatusView = label("当前未登录。", 13, ThemeUtil.muted(dark));
        content.addView(loginStatusView);
        LinearLayout loginButtons = horizontal();
        loginButton = button("登录", ThemeUtil.accent(dark));
        loginButton.setOnClickListener(view -> openLoginDialog());
        logoutButton = button("退出登录", ThemeUtil.accentSoft(dark));
        logoutButton.setTextColor(ThemeUtil.accent(dark));
        logoutButton.setOnClickListener(view -> logout());
        loginButtons.addView(loginButton);
        loginButtons.addView(logoutButton);
        content.addView(loginButtons, verticalParams(6));
        addHint(
                "账号密码只在登录弹窗中提交，密码不会保存；勾选保持登录时，"
                        + "仅将服务器返回的会话加密保存在应用目录。"
        );

        manifestInput = editText("HTTPS 更新清单 JSON 地址", false);
        manifestInput.setText(settings.getString(
                "update_manifest_url",
                AppSettings.DEFAULT_MANIFEST
        ));
        addSetting(
                "自更新清单",
                manifestInput,
                "清单包含 version、url、sha256、size 和可选 notes。"
                        + "下载后校验 SHA-256，再打开 Android 系统安装确认。"
        );
        autoUpdateCheck = checkBox(
                "启动后自动检查",
                settings.getBoolean("auto_check_update", true)
        );
        addSetting(
                "自动检查",
                autoUpdateCheck,
                "仅在应用启动后读取清单；不会在后台静默安装，"
                        + "最终安装仍由 Android 系统确认。"
        );
        updateButton = button("检查更新", ThemeUtil.accent(dark));
        updateButton.setOnClickListener(view -> checkUpdate(true));
        updateStatusView = label("尚未检查更新。", 13, ThemeUtil.muted(dark));
        content.addView(updateButton);
        content.addView(updateStatusView, verticalParams(6));

        addSection("下载任务");
        statusView = label("正在初始化内嵌下载核心...", 14, ThemeUtil.text(dark));
        content.addView(statusView);
        progressView = label("", 13, ThemeUtil.muted(dark));
        content.addView(progressView);
        progressBar = new ProgressBar(
                this,
                null,
                android.R.attr.progressBarStyleHorizontal
        );
        progressBar.setMax(100);
        progressBar.setProgress(0);
        content.addView(progressBar, verticalParams(6));

        LinearLayout actions = horizontal();
        downloadButton = button("开始下载", ThemeUtil.accent(dark));
        downloadButton.setOnClickListener(view -> startDownload());
        downloadButton.setEnabled(false);
        cancelButton = button("取消下载", ThemeUtil.accentSoft(dark));
        cancelButton.setTextColor(ThemeUtil.accent(dark));
        cancelButton.setEnabled(false);
        cancelButton.setOnClickListener(view -> cancelDownload());
        actions.addView(downloadButton);
        actions.addView(cancelButton);
        content.addView(actions, verticalParams(6));

        logView = label("运行日志\n", 13, ThemeUtil.text(dark));
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextIsSelectable(true);
        logView.setPadding(dp(10), dp(10), dp(10), dp(10));
        logView.setBackgroundColor(ThemeUtil.surface(dark));
        LinearLayout.LayoutParams logParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(220)
        );
        logParams.topMargin = dp(6);
        content.addView(logView, logParams);
        return root;
    }

    private View createHeader() {
        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(12), dp(8), dp(8), dp(8));
        header.setBackgroundColor(ThemeUtil.accentSoft(dark));

        TextView title = label("JMComic Android", 18, ThemeUtil.accent(dark));
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1
        ));

        themeSpinner = spinner(THEME_LABELS);
        selectSpinnerValue(
                themeSpinner,
                THEME_VALUES,
                settings.getString("theme", "system")
        );
        themeSpinner.setOnItemSelectedListener(new SimpleItemSelectedListener() {
            @Override
            public void onItemSelected(int position) {
                if (!themeReady) {
                    return;
                }
                String selected = THEME_VALUES[position];
                if (!selected.equals(settings.getString("theme", "system"))) {
                    settings.set("theme", selected);
                    settings.save();
                    recreate();
                }
            }
        });
        header.addView(themeSpinner, new LinearLayout.LayoutParams(
                dp(112),
                dp(44)
        ));

        Button browser = button("浏览", ThemeUtil.accent(dark));
        browser.setOnClickListener(view ->
                startActivity(new Intent(this, BrowserActivity.class))
        );
        header.addView(browser, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(44)
        ));

        Button downloads = button("结果", ThemeUtil.accent(dark));
        downloads.setOnClickListener(view ->
                startActivity(new Intent(this, DownloadsActivity.class))
        );
        header.addView(downloads, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(44)
        ));
        themeReady = true;
        return header;
    }

    private void initializePython() {
        executor.execute(() -> {
            try {
                StartupDiagnostics.record(
                        this,
                        "Python.getInstance begin"
                );
                python = Python.getInstance().getModule("jmcomic_service");
                StartupDiagnostics.record(
                        this,
                        "Python jmcomic_service loaded"
                );
            } catch (Throwable error) {
                python = null;
                StartupDiagnostics.record(
                        this,
                        "Python startup failed",
                        error
                );
                runOnUiThread(() -> showPythonStartupError(error));
                return;
            }
            JSONObject result = callPython(
                    "initialize",
                    settings.pythonConfig().toString()
            );
            runOnUiThread(() -> {
                if (result != null && result.optBoolean("ok")) {
                    initialized = true;
                    handler.post(pollRunnable);
                    statusView.setText("下载核心已就绪。先查询作品，再选择章节范围。");
                    JSONObject data = result.optJSONObject("data");
                    if (data != null) {
                        updateLoginStatus(data.optBoolean("session_active"));
                    }
                    appendLog(
                            "jmcomic 核心已加载，版本 "
                                    + dataString(data, "core_version")
                    );
                    updateActionState();
                    if (autoUpdateCheck != null
                            && autoUpdateCheck.isChecked()) {
                        handler.postDelayed(
                                () -> checkUpdate(false),
                                1200
                        );
                    }
                } else {
                    showError(result, "初始化失败");
                }
            });
        });
    }

    private void showPythonStartupError(Throwable error) {
        String detail = error == null
                ? "未知错误"
                : error.getClass().getSimpleName() + ": " + error.getMessage();
        String message = "内嵌下载核心启动失败：" + detail;
        statusView.setText(message);
        progressView.setText("诊断日志：应用目录中的 startup.log");
        appendLog(message);
        toast(message);
    }

    private void queryAlbum() {
        if (busy || downloadRunning || !initialized) {
            return;
        }
        String query = queryInput.getText().toString().trim();
        if (query.isEmpty()) {
            toast("请输入作品车号、章节车号或链接。");
            return;
        }
        saveSettings();
        setBusy(true, "正在查询作品详情...");
        queryButton.setEnabled(false);
        detailView.setText("正在查询，请稍候...");
        executor.execute(() -> {
            JSONObject result = callPython(
                    "query_album",
                    query,
                    settings.pythonConfig().toString()
            );
            runOnUiThread(() -> {
                setBusy(false, "查询结束。");
                queryButton.setEnabled(true);
                if (result == null || !result.optBoolean("ok")) {
                    showError(result, "查询失败");
                    return;
                }
                JSONObject data = result.optJSONObject("data");
                if (data == null) {
                    showError(null, "查询结果为空");
                    return;
                }
                currentAlbum = data;
                detailView.setText(data.optString("detail_text"));
                populateChapters(data);
                int count = data.optJSONArray("episodes") == null
                        ? 0
                        : data.optJSONArray("episodes").length();
                statusView.setText(
                        "查询完成，共 " + count + " 话；请选择范围后开始下载。"
                );
                downloadButton.setEnabled(true);
                appendLog(
                        "详情查询完成："
                                + data.optString("name")
                                + "（JM"
                                + data.optString("album_id")
                                + "）"
                );
            });
        });
    }

    private void populateChapters(JSONObject data) {
        JSONArray episodes = data.optJSONArray("episodes");
        List<String> labels = new ArrayList<>();
        episodeIds.clear();
        if (episodes != null) {
            for (int index = 0; index < episodes.length(); index++) {
                JSONObject episode = episodes.optJSONObject(index);
                if (episode == null) {
                    continue;
                }
                labels.add(episode.optString("label"));
                episodeIds.add(episode.optString("id"));
            }
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_item,
                labels
        );
        adapter.setDropDownViewResource(
                android.R.layout.simple_spinner_dropdown_item
        );
        chapterStartSpinner.setAdapter(adapter);
        chapterEndSpinner.setAdapter(adapter);
        chapterStartSpinner.setEnabled(!labels.isEmpty());
        chapterEndSpinner.setEnabled(!labels.isEmpty());
        if (!labels.isEmpty()) {
            chapterStartSpinner.setSelection(0);
            chapterEndSpinner.setSelection(labels.size() - 1);
            String focus = data.optString("focus_photo_id");
            int focusIndex = episodeIds.indexOf(focus);
            if (focusIndex >= 0) {
                chapterStartSpinner.setSelection(focusIndex);
                chapterEndSpinner.setSelection(focusIndex);
            }
        }
    }

    private void selectAllChapters() {
        int count = chapterStartSpinner.getAdapter() == null
                ? 0
                : chapterStartSpinner.getAdapter().getCount();
        if (count <= 0) {
            return;
        }
        chapterStartSpinner.setSelection(0);
        chapterEndSpinner.setSelection(count - 1);
    }

    private void startDownload() {
        if (busy || downloadRunning || currentAlbum == null) {
            return;
        }
        int start = chapterStartSpinner.getSelectedItemPosition();
        int end = chapterEndSpinner.getSelectedItemPosition();
        if (start < 0 || end < start) {
            toast("请选择有效的章节范围。");
            return;
        }
        saveSettings();
        try {
            JSONObject config = settings.pythonConfig();
            config.put("album_id", currentAlbum.optString("album_id"));
            config.put("start_index", start);
            config.put("end_index", end + 1);
            config.put("selected_count", end - start + 1);
            downloadRunning = true;
            busy = true;
            updateActionState();
            progressBar.setProgress(0);
            progressView.setText("准备下载...");
            statusView.setText("正在获取可下载内容...");
            appendLog(
                    "开始下载 JM"
                            + currentAlbum.optString("album_id")
                            + "，第 "
                            + (start + 1)
                            + " 到 "
                            + (end + 1)
                            + " 话"
            );
            executor.execute(() -> {
                JSONObject result = callPython(
                        "start_download",
                        config.toString()
                );
                runOnUiThread(() -> {
                    downloadRunning = false;
                    busy = false;
                    updateActionState();
                    if (result == null || !result.optBoolean("ok")) {
                        showError(result, "下载失败");
                        progressView.setText("下载失败");
                        return;
                    }
                    JSONObject data = result.optJSONObject("data");
                    statusView.setText("下载完成。");
                    progressBar.setProgress(100);
                    progressView.setText(
                            "完成图片 "
                                    + dataInt(data, "images")
                                    + " 张"
                    );
                    appendLog("下载流程结束。");
                    toast("下载完成，可在“结果”中打开文件。");
                });
            });
        } catch (JSONException error) {
            downloadRunning = false;
            busy = false;
            updateActionState();
            toast("下载配置无效：" + error.getMessage());
        }
    }

    private void cancelDownload() {
        if (!downloadRunning) {
            return;
        }
        executor.execute(() -> {
            JSONObject result = callPython("cancel_download");
            runOnUiThread(() -> {
                if (result != null && result.optBoolean("ok")) {
                    statusView.setText("已请求取消，正在停止当前任务...");
                    appendLog("已请求取消下载。");
                }
            });
        });
    }

    private void openLoginDialog() {
        if (busy || downloadRunning) {
            toast("请等待当前任务完成。");
            return;
        }
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(22), dp(8), dp(22), dp(4));

        TextView hint = label(
                "密码只用于本次登录，不会保存。保持登录时仅加密保存会话。",
                13,
                ThemeUtil.muted(dark)
        );
        layout.addView(hint);

        EditText username = editText("账号或邮箱", false);
        username.setInputType(InputType.TYPE_CLASS_TEXT);
        layout.addView(username, verticalParams(8));

        EditText password = editText("密码", false);
        password.setInputType(
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
        );
        layout.addView(password, verticalParams(4));

        CheckBox remember = checkBox("保持登录", true);
        layout.addView(remember, verticalParams(4));

        TextView dialogStatus = label("", 13, ThemeUtil.muted(dark));
        layout.addView(dialogStatus);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("登录 JMComic")
                .setView(layout)
                .setPositiveButton("登录", null)
                .setNegativeButton("取消", null)
                .create();
        dialog.setOnShowListener(ignored -> {
            Button positive = dialog.getButton(AlertDialog.BUTTON_POSITIVE);
            positive.setOnClickListener(view -> {
                String account = username.getText().toString().trim();
                String secret = password.getText().toString();
                if (account.isEmpty() || secret.isEmpty()) {
                    dialogStatus.setText("请输入账号和密码。");
                    return;
                }
                positive.setEnabled(false);
                dialogStatus.setText("正在登录...");
                saveSettings();
                executor.execute(() -> {
                    JSONObject result = callPython(
                            "login",
                            account,
                            secret,
                            remember.isChecked(),
                            settings.pythonConfig().toString()
                    );
                    password.setText("");
                    runOnUiThread(() -> {
                        if (result != null && result.optBoolean("ok")) {
                            dialog.dismiss();
                            updateLoginStatus(true);
                            appendLog("账号登录成功，后续查询和下载将使用当前会话。");
                            toast("登录成功。");
                        } else {
                            positive.setEnabled(true);
                            dialogStatus.setText(errorMessage(result, "登录失败"));
                        }
                    });
                });
            });
        });
        dialog.show();
    }

    private void logout() {
        if (busy || downloadRunning) {
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("退出登录")
                .setMessage("清除应用目录中的加密登录会话？")
                .setPositiveButton("清除", (dialog, which) ->
                        executor.execute(() -> {
                            JSONObject result = callPython("logout");
                            runOnUiThread(() -> {
                                if (result != null && result.optBoolean("ok")) {
                                    updateLoginStatus(false);
                                    appendLog("已清除登录会话。");
                                }
                            });
                        })
                )
                .setNegativeButton("取消", null)
                .show();
    }

    private void updateLoginStatus(boolean active) {
        if (loginStatusView == null) {
            return;
        }
        loginStatusView.setText(
                active
                        ? "已登录并保持会话，可用于受限作品。"
                        : "当前未登录；公开作品不受影响。"
        );
        if (logoutButton != null) {
            logoutButton.setEnabled(active);
        }
    }

    private void checkUpdate(boolean manual) {
        if (!initialized || updateCheckStarted || downloadRunning) {
            return;
        }
        updateCheckStarted = true;
        saveSettings();
        updateButton.setEnabled(false);
        updateStatusView.setText("正在检查更新...");
        executor.execute(() -> {
            JSONObject result = callPython(
                    "check_update",
                    settings.pythonConfig().toString()
            );
            runOnUiThread(() -> {
                updateCheckStarted = false;
                updateButton.setEnabled(true);
                if (result == null || !result.optBoolean("ok")) {
                    updateStatusView.setText(errorMessage(result, "检查更新失败"));
                    if (manual) {
                        toast(updateStatusView.getText().toString());
                    }
                    return;
                }
                JSONObject data = result.optJSONObject("data");
                if (data == null || !data.optBoolean("update_available")) {
                    String message = dataString(data, "message");
                    if (message.isEmpty()) {
                        message = "当前已是最新版本。";
                    }
                    updateStatusView.setText(message);
                    if (manual) {
                        toast(message);
                    }
                    return;
                }
                updateStatusView.setText(
                        "发现新版本 v"
                                + data.optString("version")
                                + "，更新包已通过 SHA-256 校验。"
                );
                launchApkInstall(new File(data.optString("path")));
            });
        });
    }

    private void launchApkInstall(File apk) {
        if (!apk.isFile()) {
            toast("更新包不存在。");
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !getPackageManager().canRequestPackageInstalls()) {
            toast("请允许本应用安装未知应用，然后再次点击检查更新。");
            Intent settingsIntent = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())
            );
            startActivity(settingsIntent);
            return;
        }
        Uri uri = FileProvider.getUriForFile(
                this,
                getPackageName() + ".files",
                apk
        );
        Intent intent = new Intent(Intent.ACTION_VIEW)
                .setDataAndType(
                        uri,
                        "application/vnd.android.package-archive"
                )
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(intent);
            appendLog("已打开系统安装器，请确认安装新版本。");
        } catch (ActivityNotFoundException error) {
            toast("系统没有可用的 APK 安装器。");
        }
    }

    private void updateProxyInput() {
        if (proxyInput == null || proxySpinner == null) {
            return;
        }
        int position = proxySpinner.getSelectedItemPosition();
        boolean manual = position >= 0
                && "manual".equals(PROXY_VALUES[position]);
        proxyInput.setEnabled(manual && !busy && !downloadRunning);
        proxyInput.setAlpha(manual ? 1.0f : 0.5f);
    }

    private void saveSettings() {
        settings.set("client", selectedValue(clientSpinner, CLIENT_VALUES));
        settings.set(
                "image_threads",
                clamp(parseInt(imageThreadsInput, 10), 1, 50)
        );
        settings.set(
                "chapter_threads",
                clamp(parseInt(chapterThreadsInput, 4), 1, 64)
        );
        settings.set("naming", selectedValue(namingSpinner, NAMING_VALUES));
        settings.set("pack_zip", packZipCheck.isChecked());
        settings.set("delete_after_zip", deleteZipCheck.isChecked());
        settings.set(
                "image_suffix",
                selectedValue(suffixSpinner, SUFFIX_VALUES)
        );
        settings.set("proxy_mode", selectedValue(proxySpinner, PROXY_VALUES));
        settings.set("proxy", proxyInput.getText().toString().trim());
        settings.set(
                "update_manifest_url",
                manifestInput.getText().toString().trim()
        );
        settings.set("auto_check_update", autoUpdateCheck.isChecked());
        settings.save();
        updateProxyInput();
    }

    private void setBusy(boolean value, String message) {
        busy = value;
        if (message != null) {
            statusView.setText(message);
        }
        updateActionState();
    }

    private void updateActionState() {
        boolean running = busy || downloadRunning;
        if (queryButton != null) {
            queryButton.setEnabled(!running && initialized);
        }
        if (downloadButton != null) {
            downloadButton.setEnabled(!running && currentAlbum != null);
        }
        if (cancelButton != null) {
            cancelButton.setEnabled(downloadRunning);
        }
        if (loginButton != null) {
            loginButton.setEnabled(!running && initialized);
        }
        if (logoutButton != null) {
            logoutButton.setEnabled(
                    !running
                            && loginStatusView != null
                            && loginStatusView.getText().toString().startsWith("已登录")
            );
        }
        if (updateButton != null) {
            updateButton.setEnabled(!running && initialized);
        }
        updateProxyInput();
    }

    private void pollPythonEvents() {
        if (python == null) {
            return;
        }
        try {
            String raw = python.callAttr("poll_events").toString();
            JSONArray events = new JSONArray(raw);
            for (int index = 0; index < events.length(); index++) {
                JSONObject event = events.optJSONObject(index);
                if (event == null) {
                    continue;
                }
                String kind = event.optString("kind");
                switch (kind) {
                    case "log":
                        appendLog(event.optString("message"));
                        break;
                    case "album":
                        appendLog(
                                "作品：" + event.optString("title")
                                        + "；已选择 "
                                        + event.optInt("selected_count")
                                        + " 话"
                        );
                        break;
                    case "chapter":
                        progressView.setText(
                                "正在下载 第"
                                        + event.optInt("chapter_index")
                                        + "话 "
                                        + event.optString("chapter_name")
                                        + "（"
                                        + event.optInt("image_count")
                                        + " 张）"
                        );
                        break;
                    case "progress":
                        updateProgress(
                                event.optInt("completed"),
                                event.optInt("total")
                        );
                        break;
                    case "export":
                        appendLog("生成文件：" + event.optString("path"));
                        break;
                    case "done":
                        if (event.optBoolean("success")) {
                            appendLog("任务执行成功。");
                        } else {
                            appendLog(
                                    "任务结束："
                                            + event.optString("error")
                            );
                        }
                        break;
                    case "update":
                        updateStatusView.setText(event.optString("message"));
                        break;
                    case "login":
                        updateLoginStatus(event.optBoolean("active"));
                        break;
                    default:
                        break;
                }
            }
        } catch (RuntimeException | JSONException ignored) {
        }
    }

    private void updateProgress(int completed, int total) {
        if (total <= 0) {
            progressBar.setIndeterminate(true);
            progressView.setText("已下载 " + completed + " 张");
            return;
        }
        progressBar.setIndeterminate(false);
        int percent = Math.min(
                Math.round(completed * 100.0f / total),
                100
        );
        progressBar.setProgress(percent);
        progressView.setText(
                String.format(
                        Locale.US,
                        "已下载 %d / %d 张（%d%%）",
                        completed,
                        total,
                        percent
                )
        );
    }

    private JSONObject callPython(String method, Object... arguments) {
        try {
            if (python == null) {
                return errorJson("Python 运行环境尚未加载。");
            }
            String raw = python.callAttr(method, arguments).toString();
            return new JSONObject(raw);
        } catch (Throwable error) {
            return errorJson(error.getMessage());
        }
    }

    private JSONObject errorJson(String message) {
        JSONObject result = new JSONObject();
        try {
            result.put("ok", false);
            result.put("error", message == null ? "未知错误" : message);
        } catch (JSONException ignored) {
        }
        return result;
    }

    private void showError(JSONObject result, String fallback) {
        String message = errorMessage(result, fallback);
        statusView.setText(message);
        appendLog(message);
        toast(message);
    }

    private String errorMessage(JSONObject result, String fallback) {
        if (result == null) {
            return fallback;
        }
        String message = result.optString("error");
        return message.isEmpty() ? fallback : message;
    }

    private void appendLog(String message) {
        if (message == null || message.isEmpty()) {
            return;
        }
        String current = logView.getText().toString();
        if (current.length() > 24000) {
            current = current.substring(current.length() - 16000);
        }
        logView.setText(current + message + "\n");
    }

    private void addSection(String title) {
        TextView view = label(title, 18, ThemeUtil.accent(dark));
        view.setTypeface(Typeface.DEFAULT_BOLD);
        content.addView(view, verticalParams(18));
        View divider = new View(this);
        divider.setBackgroundColor(ThemeUtil.border(dark));
        LinearLayout.LayoutParams dividerParams =
                new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(1)
        );
        dividerParams.topMargin = dp(4);
        content.addView(divider, dividerParams);
    }

    private void addSetting(String title, View control, String description) {
        TextView label = label(title, 15, ThemeUtil.text(dark));
        label.setTypeface(Typeface.DEFAULT_BOLD);
        content.addView(label, verticalParams(12));
        content.addView(control, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        addHint(description);
    }

    private void addHint(String text) {
        TextView hint = label(text, 12, ThemeUtil.muted(dark));
        hint.setLineSpacing(0, 1.15f);
        content.addView(hint, verticalParams(5));
    }

    private LinearLayout horizontal() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        return layout;
    }

    private LinearLayout.LayoutParams verticalParams(int topMargin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        params.topMargin = dp(topMargin);
        return params;
    }

    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.12f);
        return view;
    }

    private EditText editText(String hint, boolean number) {
        EditText view = new EditText(this);
        view.setHint(hint);
        view.setSingleLine(true);
        view.setTextSize(14);
        view.setTextColor(ThemeUtil.text(dark));
        view.setHintTextColor(ThemeUtil.muted(dark));
        view.setPadding(dp(12), dp(4), dp(12), dp(4));
        view.setBackgroundTintList(
                ColorStateList.valueOf(ThemeUtil.accent(dark))
        );
        if (number) {
            view.setInputType(
                    InputType.TYPE_CLASS_NUMBER
                            | InputType.TYPE_NUMBER_FLAG_DECIMAL
            );
        }
        return view;
    }

    private Spinner spinner(String[] values) {
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this,
                android.R.layout.simple_spinner_item,
                values
        );
        adapter.setDropDownViewResource(
                android.R.layout.simple_spinner_dropdown_item
        );
        spinner.setAdapter(adapter);
        spinner.setBackgroundTintList(
                ColorStateList.valueOf(ThemeUtil.accent(dark))
        );
        spinner.setPadding(dp(8), 0, dp(8), 0);
        return spinner;
    }

    private CheckBox checkBox(String text, boolean checked) {
        CheckBox view = new CheckBox(this);
        view.setText(text);
        view.setTextSize(14);
        view.setTextColor(ThemeUtil.text(dark));
        view.setChecked(checked);
        view.setButtonTintList(
                ColorStateList.valueOf(ThemeUtil.accent(dark))
        );
        view.setPadding(dp(4), dp(6), dp(4), dp(6));
        return view;
    }

    private Button button(String text, int background) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setMinHeight(dp(44));
        button.setTextColor(
                background == ThemeUtil.accent(dark)
                        ? (dark ? Color.rgb(8, 20, 20) : Color.WHITE)
                        : ThemeUtil.text(dark)
        );
        button.setBackgroundTintList(ColorStateList.valueOf(background));
        button.setPadding(dp(12), 0, dp(12), 0);
        return button;
    }

    private void styleTree(View view) {
        if (view instanceof TextView) {
            TextView textView = (TextView) view;
            textView.setHintTextColor(ThemeUtil.muted(dark));
        }
        if (view instanceof CheckBox) {
            ((CheckBox) view).setButtonTintList(
                    ColorStateList.valueOf(ThemeUtil.accent(dark))
            );
        }
        if (view instanceof ProgressBar) {
            ((ProgressBar) view).setProgressTintList(
                    ColorStateList.valueOf(ThemeUtil.accent(dark))
            );
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int index = 0; index < group.getChildCount(); index++) {
                styleTree(group.getChildAt(index));
            }
        }
    }

    private void selectSpinnerValue(
            Spinner spinner,
            String[] values,
            String value
    ) {
        for (int index = 0; index < values.length; index++) {
            if (values[index].equals(value)) {
                spinner.setSelection(index);
                return;
            }
        }
    }

    private String selectedValue(Spinner spinner, String[] values) {
        int position = spinner.getSelectedItemPosition();
        if (position < 0 || position >= values.length) {
            return values[0];
        }
        return values[position];
    }

    private int parseInt(EditText input, int fallback) {
        try {
            return Integer.parseInt(input.getText().toString().trim());
        } catch (NumberFormatException error) {
            return fallback;
        }
    }

    private int clamp(int value, int minimum, int maximum) {
        return Math.max(minimum, Math.min(value, maximum));
    }

    private String dataString(JSONObject data, String key) {
        return data == null ? "" : data.optString(key);
    }

    private int dataInt(JSONObject data, String key) {
        return data == null ? 0 : data.optInt(key);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private int dp(int value) {
        return Math.round(
                value * getResources().getDisplayMetrics().density
        );
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (updateCheckStarted && updateButton != null) {
            updateButton.setEnabled(!busy);
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(pollRunnable);
        executor.shutdownNow();
        super.onDestroy();
    }

    private abstract static class SimpleItemSelectedListener
            implements android.widget.AdapterView.OnItemSelectedListener {
        @Override
        public void onNothingSelected(android.widget.AdapterView<?> parent) {
        }

        @Override
        public final void onItemSelected(
                android.widget.AdapterView<?> parent,
                View view,
                int position,
                long id
        ) {
            onItemSelected(position);
        }

        public abstract void onItemSelected(int position);
    }
}
