# Flutter SDK 配置指南

## 获取 SDK

提示

获取 SDK 有多种方式，较为推荐的方式是通过**包依赖管理工具** 下载最新版本。

SDK 发布在 pub.dev:

* [数据存储 SDK](https://pub.dev/packages/leancloud_storage)
* [即时通讯 SDK](https://pub.dev/packages/leancloud_official_plugin)

### 使用数据存储

在 `pubspec.yaml` 中，将 SDK 添加到依赖项列表:

    dependencies:
      flutter:
        sdk: flutter
      ...
      leancloud_storage: ^0.7.10

### 使用即时通讯

即时通讯的 Flutter 插件 SDK 基于 [Swift SDK](https://github.com/leancloud/swift-sdk) 以及 [Java Unified SDK](https://github.com/leancloud/java-unified-sdk) 开发。

#### 第一步

在 `pubspec.yaml` 中，将 SDK 添加到依赖项列表:

    dependencies:
      flutter:
        sdk: flutter
      ...
      leancloud_official_plugin: ^1.0.1

#### 第二步

**Android 开发者** 要配置 Gradle 安装 Java Unified SDK，打开工程目录 `android/app/build.gradle`，添加如下依赖：

    dependencies {
      implementation 'cn.leancloud:storage-android:8.2.28'
      implementation 'cn.leancloud:realtime-android:8.2.28'
      implementation 'io.reactivex.rxjava2:rxandroid:2.1.1'
    }

**iOS 开发者** 需要通过 CocoaPods 安装 Swift SDK：

    cd ios/
    pod update # 或者 $ pod install --repo-update

## 初始化

### 应用凭证

在 **云服务控制台 > 设置 > 应用凭证** 可以查看应用的基本信息：

* **App ID** ：在 SDK 初始化时用到。
* **App Key** ：客户端对服务端的调用凭证，在 SDK 初始化时用到。
* **Master Key** ：用于在自有服务器、云引擎等**受信任环境** 调用管理接口，具备跳过一切权限验证的超级权限。所以**一定注意保密，千万不要在客户端代码中使用该凭证** 。
* **服务器地址** ：又称 API 域名或 **Server URL** ，在客户端 SDK 初始化时用到。域名配置参考下一节[域名](#%E5%9F%9F%E5%90%8D)。

### 数据存储

使用 SDK 时添加下列导入语句到头部：

    import'package:leancloud_storage/leancloud.dart';

然后在 lib/main.dart 设置：

    LeanCloud.initialize(
    'your-app-id','your-app-key',
        server:'https://your_server_url',
        queryCache:newLCQueryCache());

国际版应用不要求绑定自定义域名。 如果你的国际版应用（App ID 后缀为 `-MdYXbMMI`）没有绑定自定义域名，**初始化 SDK 时不用传入服务器地址参数** 。 极个别 App ID 后缀不为 `-MdYXbMMI` 的国际版应用，请参见[这里的说明](../../domain/guide/#app-id-%E5%90%8E%E7%BC%80%E4%B8%8D%E4%B8%BA--mdyxbmmi-%E7%9A%84%E5%9B%BD%E9%99%85%E7%89%88%E5%BA%94%E7%94%A8%E5%A6%82%E4%BD%95%E5%88%9D%E5%A7%8B%E5%8C%96-sdk)。

#### Android 权限设置

别忘了在 `AndroidManifest.xml` 里声明所需的 Android 权限：

    <uses-permissionandroid:name="android.permission.INTERNET"/>
    <uses-permissionandroid:name="android.permission.ACCESS_NETWORK_STATE"/>

### 即时通讯

使用 SDK 时添加下列导入语句到头部：

    import'package:leancloud_official_plugin/leancloud_plugin.dart';

**使用 Flutter 即时通讯插件需要在 Android 和 iOS 平台分别初始化。**

#### Android 平台初始化

首先向 Application 类的 onCreate 方法添加：

    importcn.leancloud.LeanCloud;
    importcn.leancloud.LCLogger;
    importcn.leancloud.im.LCIMOptions;
    importio.flutter.app.FlutterApplication;

    publicclassMyLeanCloudAppextendsFlutterApplication{
    @Override
    publicvoidonCreate(){
    super.onCreate();
    //开启未读消息数更新通知
    LCIMOptions.getGlobalOptions().setUnreadNotificationEnabled(true);
    //开启调试日志
    LeanCloud.setLogLevel(LCLogger.Level.DEBUG);
    // 提供 this、App ID、App Key、Server URL 作为参数
    // 请将 your_server_url 替换为你的应用绑定的 API 域名
    LeanCloud.initialize(this,"your-app-id","your-app-key","https://your_server_url");
    }
    }

然后指定 SDK 需要的权限并在 AndroidManifest.xml 里面声明 MyLeanCloudApp 类：

    <uses-permissionandroid:name="android.permission.INTERNET"/>
    <uses-permissionandroid:name="android.permission.ACCESS_NETWORK_STATE"/>

    <application
    …
    android:name=".MyLeanCloudApp">

    <serviceandroid:name="cn.leancloud.push.PushService"/>
    <receiverandroid:name="cn.leancloud.push.LCBroadcastReceiver">
    <intent-filter>
    <actionandroid:name="android.intent.action.BOOT_COMPLETED"/>
    <actionandroid:name="android.intent.action.USER_PRESENT"/>
    <actionandroid:name="android.net.conn.CONNECTIVITY_CHANGE"/>
    </intent-filter>
    </receiver>

    </application>

#### iOS 平台初始化

在 AppDelegate.swift 中加入如下初始化代码：

    importFlutter
    importLeanCloud

    @UIApplicationMain
    @objcclassAppDelegate:FlutterAppDelegate{
    overridefuncapplication(
    _ application:UIApplication,
            didFinishLaunchingWithOptions launchOptions:[UIApplication.LaunchOptionsKey:Any]?
    )->Bool{
    do{
    LCApplication.logLevel =.all
    tryLCApplication.default.set(
                    id:"your-app-id",
                    key:"your-app-key",
                    serverURL:"https://your_server_url")
    GeneratedPluginRegistrant.register(with:self)
    returnsuper.application(application, didFinishLaunchingWithOptions: launchOptions)
    }catch{
    fatalError("\(error)")
    }
    }
    }

## 域名

请参考 [域名绑定指南](../../domain/guide/)。

## 开启调试日志

在应用开发阶段，你可以选择开启 SDK 的调试日志（debug log）来方便追踪问题。调试日志开启后，SDK 会把网络请求、错误消息等信息输出到 IDE 的日志窗口，或是浏览器 Console 或是云引擎日志（如果在云引擎下运行 SDK）。

数据存储服务开启调试日志：

    // 在 LeanCloud.initialize 初始化之后执行
    LCLogger.setLevel(LCLogger.DebugLevel);

即时通讯服务开启调试日志方式同 Swift SDK 与 Java Unified SDK。

注意，在应用发布之前，请关闭调试日志，以免暴露敏感数据。

## 验证

首先，确认本地网络环境是可以访问云端服务器的，可以执行以下命令：

    curl "https://{{host}}/1.1/date"

`{{host}}` 为绑定的 API 自定义域名。

如果当前网络正常会返回当前时间：

    {"__type":"Date","iso":"2020-10-12T06:46:56.000Z"}

然后在项目 lib/main.dart 中编写如下测试代码：

    LCObject object =LCObject('TestObject');
    object['words']='Hello world!';
    await object.save();

保存后运行程序。

然后打开 **云服务控制台 > 数据存储 > 结构化数据 > `TestObject`**，如果看到数据表中出现一行「words」列的值为「Hello world!」的数据，说明 SDK 已经正确地执行了上述代码，配置完毕。

如果控制台没有发现对应的数据，请参考 [问题排查](#%E9%97%AE%E9%A2%98%E6%8E%92%E6%9F%A5)。

## 问题排查

SDK 安装指南基于当前最新版本的 SDK 编写，所以排查问题前，请先检查下安装的 SDK 是不是最新版本。

### `401 Unauthorized`

如果 SDK 抛出 `401` 异常或者查看本地网络访问日志存在：

    {
    "code":401,
    "error":"Unauthorized."
    }

则可认定为 App ID 或者 App Key 输入有误，或者是不匹配，很多开发者同时注册了多个应用，导致拷贝粘贴的时候，用 A 应用的 App ID 匹配 B 应用的 App Key，这样就会出现服务端鉴权失败的错误。

### 客户端无法访问网络

客户端尤其是手机端，应用在访问网络的时候需要申请一定的权限。
