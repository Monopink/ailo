# Swift SDK 配置指南

## 获取 SDK

获取 SDK 有多种方式，较为推荐的方式是通过包依赖管理工具下载最新版本。

### 包依赖管理工具安装

通过 [CocoaPods](https://cocoapods.org) 或者 [Swift Package Manager](https://developer.apple.com/documentation/swift_packages) 安装可以最大化地简化安装过程。

#### CocoaPods

首先，确保开发环境中已经安装了最新版 `pod`。如果没有，请参考官网的 [INSTALL](https://cocoapods.org) 文档。

接着，在项目根目录下通过命令行工具执行下列命令生成 `Podfile` 文件：

    pod init

参考 [GET STARTED](https://cocoapods.org) 文档，在 `Podfile` 文件中的 `target` 里添加 pod 依赖：

    pod 'LeanCloud'

或者使用 [Subspecs](https://guides.cocoapods.org/syntax/podspec.html#subspec) 方式：

    pod 'LeanCloud/Foundation' # 数据存储、短信、推送、云引擎等基础服务模块，必选
    pod 'LeanCloud/RTM'        # 即时通讯、LiveQuery 模块，可选

注意

`LeanCloud/RTM` 依赖了 `LeanCloud/Foundation`，所以不同模块的版本号必需保持一致。

最后，在项目根目录下执行下列任意命令，集成最新的 SDK：

    pod update

或者

    pod install --repo-update

集成 SDK 成功后，使用项目根目录下 **`<项目名称>.xcworkspace`** 来打开项目。

#### Swift Package Manager

参考 [Apple 官方提供的集成文档](https://developer.apple.com/documentation/xcode/adding_package_dependencies_to_your_app)，添加 [Swift SDK Repo](https://github.com/leancloud/swift-sdk) 即可。

### 手动安装

备注

下载 Swift SDK 源码后，也需要等待 Swift Package Manager 下载并集成其他依赖，所以**推荐直接使用 Swift Package Manager** 。

## 初始化

打开 `AppDelegate.swift` 文件，添加下列导入语句到头部：

    importLeanCloud

然后在 `application(_:didFinishLaunchingWithOptions:)` 函数内设置初始化参数：

    do{
    tryLCApplication.default.set(
            id: your-app-id,
            key: your-app-key,
            serverURL:"https://your_server_url")
    }catch{
    print(error)
    }

信息

在使用 SDK 的 API 时，请确保进行了 Application 的 ID、Key 以及 Server URL（API 域名）的初始化。

国际版应用不要求绑定自定义域名。 如果你的国际版应用（App ID 后缀为 `-MdYXbMMI`）没有绑定自定义域名，**初始化 SDK 时不用传入服务器地址参数** 。 极个别 App ID 后缀不为 `-MdYXbMMI` 的国际版应用，请参见[这里的说明](../../domain/guide/#app-id-%E5%90%8E%E7%BC%80%E4%B8%8D%E4%B8%BA--mdyxbmmi-%E7%9A%84%E5%9B%BD%E9%99%85%E7%89%88%E5%BA%94%E7%94%A8%E5%A6%82%E4%BD%95%E5%88%9D%E5%A7%8B%E5%8C%96-sdk)。

    //国际版应用初始化：
    do{
    tryLCApplication.default.set(
            id: your-app-id,
            key: your-app-key)
    }catch{
    print(error)
    }

### 应用凭证

在 **云服务控制台 > 设置 > 应用凭证** 可以查看应用的基本信息：

* **App ID** ：在 SDK 初始化时用到。
* **App Key** ：客户端对服务端的调用凭证，在 SDK 初始化时用到。
* **Master Key** ：用于在自有服务器、云引擎等**受信任环境** 调用管理接口，具备跳过一切权限验证的超级权限。所以**一定注意保密，千万不要在客户端代码中使用该凭证** 。
* **服务器地址** ：又称 API 域名或 **Server URL** ，在客户端 SDK 初始化时用到。域名配置参考下一节[域名](#%E5%9F%9F%E5%90%8D)。

## 域名

请参考 [域名绑定指南](../../domain/guide/)。

## 开启调试日志

在应用开发阶段，你可以选择开启 SDK 的调试日志（debug log）来方便追踪问题。调试日志开启后，SDK 会把网络请求、错误消息等信息输出到 IDE 的日志窗口，或是浏览器 Console 或是云引擎日志（如果在云引擎下运行 SDK）。

    // 在 Application 初始化代码执行之前执行
    LCApplication.logLevel =.all

注意，在应用发布之前，请关闭调试日志，以免暴露敏感数据。

## 验证

首先，确认本地网络环境是可以访问云端服务器的，可以执行以下命令：

    curl "https://{{host}}/1.1/date"

`{{host}}` 为绑定的 API 自定义域名。

如果当前网络正常会返回当前时间：

    {"__type":"Date","iso":"2020-10-12T06:46:56.000Z"}

下面来试着向 LeanCloud 云端保存一条数据。

将下面的代码拷贝到 `viewDidLoad` 函数或其他在应用运行时会被调用的函数中：

    do{
    let testObject =LCObject(className:"TestObject")
    try testObject.set("words", value:"Hello world!")
    let result = testObject.save()
    iflet error = result.error {
    print(error)
    }
    }catch{
    print(error)
    }

然后，点击 `Run` 运行调试，真机和虚拟机均可。

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
