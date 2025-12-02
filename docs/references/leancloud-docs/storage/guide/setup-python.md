# Python SDK 配置指南

信息

Python SDK 为服务端 SDK，主要用于在云引擎等受信任的服务器环境中调用管理接口、云函数等。 如果你需要在自己的服务器上使用 Python SDK 调用数据存储、即时通讯、推送等服务，请参考此篇文档完成配置。

## 获取 SDK

获取 SDK 有多种方式，较为推荐的方式是通过包依赖管理工具下载最新版本。

### 包依赖管理工具安装

使用 pip 安装：

    pip install leancloud

取决于系统环境，可能需要在命令前加 `sudo`。

### 手动安装

前往 [Python SDK 下载页](https://releases.leanapp.cn/#/leancloud/python-sdk/releases)获取 SDK 并安装。

## 初始化

调用 `init` 方法进行初始化：

    import leancloud

    leancloud.init("your-app-id","your-app-key")
    # 或者使用 Master Key
    # leancloud.init("your-app-id", master_key="your-master-key")

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

    # 写在启动脚本的头部
    # 如果是在云引擎环境，启动脚本是 wsgi.py
    import logging

    logging.basicConfig(level=logging.DEBUG)

注意，在应用发布之前，请关闭调试日志，以免暴露敏感数据。

## 验证

首先，确认本地网络环境是可以访问云端服务器的，可以执行以下命令：

    curl "https://{{host}}/1.1/date"

`{{host}}` 为绑定的 API 自定义域名。

如果当前网络正常会返回当前时间：

    {"__type":"Date","iso":"2020-10-12T06:46:56.000Z"}

然后在项目中编写如下测试代码：

    TestObject = leancloud.Object.extend('TestObject')
    test_object = TestObject()
    test_object.set('words',"Hello world!")
    test_object.save()

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

则可认定为 `App ID` 或者 `App Key` 输入有误，或者是不匹配，很多开发者同时注册了多个应用，导致拷贝粘贴的时候，用 A 应用的 `App ID` 匹配 B 应用的 `App Key`，这样就会出现服务端鉴权失败的错误。

### 客户端无法访问网络

客户端尤其是手机端，应用在访问网络的时候需要申请一定的权限。
