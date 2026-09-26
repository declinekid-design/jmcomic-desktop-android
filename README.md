# JMComic Desktop and Android

Windows 桌面端和 Android 浏览版的 JMComic 图形化工具。桌面端围绕
[hect0x7/JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)
提供的 Python API 构建，提供作品查询、章节范围选择、批量下载、ZIP 打包、
账号登录、自更新和内置漫画站浏览。

> **致谢**
>
> 本项目基于 hect0x7 的开源项目
> [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)
> 实现。感谢作者和所有贡献者提供 API、下载器、插件系统和文档。
> 上游项目使用 MIT License，原始版权声明保留在 [LICENSE](LICENSE) 中。

## 功能

### Windows 桌面版 1.5.0

- 输入车号、JM 编号、章节编号或禁漫链接。
- 查询标题、作者、日期、观看、点赞、评论、标签和完整章节列表。
- 选择从第几话下载到第几话。
- 按车号或漫画名创建作品目录。
- 多话作品可生成 ZIP，ZIP 内按“第几话 话名”分文件夹。
- 浅色、深色、跟随系统三种主题。
- 账号密码登录和加密会话保持。
- 自更新清单检查、SHA-256 校验、失败回滚。
- 内置 Qt WebEngine 浏览器，可打开漫画站挑选作品。
- 配置、缓存、日志和下载数据默认保存在程序目录。

![桌面端深色界面](docs/images/desktop-dark.png)

![内置浏览器](docs/images/browser-dark.png)

### Android 浏览版 1.0.0

- 默认打开 `https://comic18j-hbd.space/`。
- 支持返回、刷新和下载记录。
- 网页登录 Cookie 由 Android WebView 保持。
- 下载交给 Android DownloadManager。
- 图片下载可以在应用内顺序阅读。

Android 版是浏览器封装，不包含桌面端的完整章节下载和 ZIP 打包逻辑。

## 目录

```text
desktop/   Windows PySide6 桌面端源码、PyInstaller 配置和构建脚本
android/   Android WebView 源码和 APK 构建脚本
artifacts/ Android 1.0.0 debug APK
docs/      截图和说明
```

## Windows 桌面端构建

需要 Python 3.12 和 PowerShell：

```powershell
cd desktop
.\build.ps1
```

脚本会创建仓库根目录下的 `.venv`，安装 `PySide6 6.8.3`、
`PyInstaller` 和上游 `jmcomic 2.7.7`，然后生成：

```text
dist/JMComicDesktop/
dist/JMComicDesktopUpdater/
```

## Android APK 构建

需要 JDK 17、Android Platform 35 和 Build-Tools 35.0.0：

```powershell
$env:JAVA_HOME = 'C:\path\to\jdk-17'
$env:ANDROID_HOME = 'C:\path\to\android-sdk'
$env:ANDROID_USER_HOME = 'C:\path\to\android-user-home'
$env:GRADLE_USER_HOME = 'C:\path\to\gradle-home'

.\android\scripts\build_apk.ps1 `
  -ToolchainRoot 'C:\path\to\android-toolchain'
```

默认输出为首选构建目录中的 `JMComicBrowser-1.0.0-debug.apk`。仓库中的
`artifacts/JMComicBrowser-1.0.0-debug.apk` 是已构建的 Android 8.0+
debug 包，SHA-256 为：

```text
190AA0B04BCECAD5BCA855012D7DA10BAD55EBC505FC2140131624C673694F7E
```

## 数据与隐私

Windows 桌面版不把配置、浏览器缓存或登录会话写入 `%APPDATA%`，默认全部放在
主程序目录下的 `data` 和 `downloads`。

Android 版的 WebView Cookie 由 Android 应用沙箱管理。仓库不包含实际账号、
密码、登录会话或下载的漫画内容。

## 免责声明

本项目仅提供第三方开源 API 的图形界面和技术示例。第三方站点的内容由其运营者
提供，请确认你已成年，并确认访问、下载和保存相关内容符合当地法律及站点条款。
请勿将本项目用于侵权、未授权传播或其他违法用途。

