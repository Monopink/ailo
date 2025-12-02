# 一，从简单的单聊、群聊、收发图文消息开始

## 阅读准备

在阅读本章之前，如果你还不太了解即时通讯服务的总体架构，建议先阅读[即时通讯服务总览](overview/)。 另外，如果你还没有下载对应开发环境（语言）的 SDK，请参考相应语言的 SDK 配置指南完成 SDK 安装与初始化：

* [Java SDK 配置](../../storage/guide/setup-java/)
* [Objective-C SDK 配置](../../storage/guide/setup-objc/)
* [JavaScript SDK 配置](../../storage/guide/setup-js/)
* [Swift SDK 配置](../../storage/guide/setup-swift/)
* [Flutter SDK 配置](../../storage/guide/setup-flutter/)

## 本章导读

在很多产品里面，都存在让用户实时沟通的需求，例如：

* 员工与客户之间的实时交流，如房地产行业经纪人与客户的沟通，商业产品客服与客户的沟通，等等。
* 企业内部沟通协作，如内部的工作流系统、文档／知识库系统，增加实时互动的方式可能就会让工作效率得到极大提升。
* 直播互动，不论是文体行业的大型电视节目中的观众互动、重大赛事直播，娱乐行业的游戏现场直播、网红直播，还是教育行业的在线课程直播、KOL 知识分享，在支持超大规模用户积极参与的同时，也需要做好内容审核管理。
* 应用内社交，游戏公会嗨聊，等等。社交产品要能长时间吸引住用户，除了实时性之外，还需要更多的创新玩法，对于标准化通讯服务会存在更多的功能扩展需求。

根据功能需求的层次性和技术实现的难易程度不同，我们分为多篇文档来一步步地讲解如何利用即时通讯服务实现不同业务场景需求：

* 本篇文档，我们会从实现简单的单聊／群聊开始，演示创建和加入「对话」、发送和接收富媒体「消息」的流程，同时让大家了解历史消息云端保存与拉取的机制，希望可以满足在成熟产品中快速集成一个简单的聊天页面的需求。
* [离线消息文档](intermediate/)会介绍一些特殊消息的处理，例如 @ 成员提醒、撤回和修改、消息送达和被阅读的回执通知等，离线状态下的推送通知和消息同步机制，多设备登录的支持方案，以及如何扩展自定义消息类型，希望可以满足一个社交类产品的多方面需求。
* [权限与聊天室文档](senior/)会介绍一下系统的安全机制，包括第三方的操作签名，同时也会介绍直播聊天室和临时对话的用法，希望可以帮助开发者提升产品的安全性和易用性，并满足特殊场景的需求。
* [Hook 与系统对话文档](systemconv/)会介绍即时通讯服务端 Hook 机制，系统对话的用法，以及给出一个基于这两个功能打造一个属于自己的聊天机器人的方案，希望可以满足业务层多种多样的扩展需求。

希望开发者最终顺利完成产品开发的同时，也对即时通讯服务的体系结构有一个清晰的了解，以便于产品的长期维护和定制化扩展。

## 一对一单聊

在开始讨论聊天之前，我们需要介绍一下在即时通讯 SDK 中的 `IMClient` 对象：

> `IMClient` 对应实体的是一个用户，它代表着一个用户以客户端的身份登录到了即时通讯的系统。

具体可以参考[即时通讯服务总览](overview/)中《clientId、用户和登录》一节的说明。

### 创建 `IMClient`

假设我们产品中有一个叫「Tom」的用户，首先我们在 SDK 中创建出一个与之对应的 `IMClient` 实例（创建实例前请确保已经成功初始化了 SDK）：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    LCIMClient tom =newLCIMClient("Tom");

    // clientId 为 Tom
    LCIMClient tom =LCIMClient.getInstance("Tom");

    // 定义一个常驻内存的属性变量
    @property(nonatomic) LCIMClient *tom;
    // 初始化
    NSError *error;
    tom =[[LCIMClient alloc] initWithClientId:@"Tom" error:&error];
    if(error){
    NSLog(@"init failed with error: %@", error);
    }else{
    NSLog(@"init succeeded");
    }

    // Tom 用自己的名字作为 clientId 来登录即时通讯服务
    realtime
    .createIMClient("Tom")
    .then(function(tom){
    // 成功登录
    })
    .catch(console.error);

    // 定义一个常驻内存的全局变量
    var tom:IMClient
    // 初始化
    do{
        tom =tryIMClient(ID:"Tom")
    }catch{
    print(error)
    }

    // clientId 为 Tom
    Client tom =Client(id:'Tom');

注意这里一个 `IMClient` 实例就代表一个终端用户，我们需要把它全局保存起来，因为后续该用户在即时通讯上的所有操作都需要直接或者间接使用这个实例。

### 登录即时通讯服务器

创建好了「Tom」这个用户对应的 `IMClient` 实例之后，我们接下来需要让该实例「登录」即时通讯服务器。 只有登录成功之后客户端才能开始与其他用户聊天，也才能接收到云端下发的各种事件通知。

这里需要说明一点，有些 SDK（比如 C# SDK）在创建 `IMClient` 实例的同时会自动进行登录，另一些 SDK（比如 iOS 和 Android SDK）则需要调用开发者手动执行 `open` 方法进行登录：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await tom.Open();

    // Tom 创建了一个 client，用自己的名字作为 clientId 登录
    LCIMClient tom =LCIMClient.getInstance("Tom");
    // Tom 登录
    tom.open(newLCIMClientCallback(){
    @Override
    publicvoiddone(LCIMClient client,LCIMException e){
    if(e ==null){
    // 成功打开连接
    }
    }
    });

    // 定义一个常驻内存的属性变量
    @property(nonatomic) LCIMClient *tom;
    // 初始化，然后登录
    NSError *error;
    tom =[[LCIMClient alloc] initWithClientId:@"Tom" error:&error];
    if(error){
    NSLog(@"init failed with error: %@", error);
    }else{
    [tom openWithCallback:^(BOOL succeeded, NSError * _Nullable error){
    if(succeeded){
    // open succeeded
    }
    }];
    }

    // Tom 用自己的名字作为 clientId 登录，并且获取 IMClient 对象实例
    realtime
    .createIMClient("Tom")
    .then(function(tom){
    // 成功登录
    })
    .catch(console.error);

    // 定义一个常驻内存的全局变量
    var tom:IMClient
    // 初始化，然后登录
    do{
        tom =tryIMClient(ID:"Tom")
        tom.open{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    // Tom 创建了一个 client，用自己的名字作为 clientId 登录
    Client tom =Client(id:'Tom');
    // Tom 登录
    await tom.open();

### 使用 `_User` 登录

除了应用层指定 `clientId` 登录之外，我们也支持直接使用 `_User` 对象来创建 `IMClient` 并登录。这种方式能直接利用云端内置的用户鉴权系统而省掉登录签名操作，更方便地将存储和即时通讯这两个模块结合起来使用。示例代码如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var user =await LCUser.Login("USER_NAME","PASSWORD");
    var client =newLCIMClient(user);

    // 以 LCUser 的用户名和密码登录到存储服务
    LCUser.logIn("Tom","cat!@#123").subscribe(newObserver<LCUser>(){
    publicvoidonSubscribe(Disposable disposable){}
    publicvoidonNext(LCUser user){
    // 登录成功，与服务器连接
    LCIMClient client =LCIMClient.getInstance(user);
            client.open(newLCIMClientCallback(){
    @Override
    publicvoiddone(finalLCIMClient avimClient,LCIMException e){
    // 执行其他逻辑
    }
    });
    }
    publicvoidonError(Throwable throwable){
    // 登录失败（可能是密码错误）
    }
    publicvoidonComplete(){}
    });

    // 定义一个常驻内存的属性变量
    @property(nonatomic) LCIMClient *client;
    // 登录 User，然后使用登录成功的 User 初始化 Client 并登录
    [LCUser logInWithUsernameInBackground:USER_NAME password:PASSWORD block:^(LCUser * _Nullable user, NSError * _Nullable error){
    if(user){
            NSError *err;
            client =[[LCIMClient alloc] initWithUser:user error:&err];
    if(err){
    NSLog(@"init failed with error: %@", err);
    }else{
    [client openWithCallback:^(BOOL succeeded, NSError * _Nullable error){
    if(succeeded){
    // open succeeded
    }
    }];
    }
    }
    }];

    varAV=require("leancloud-storage");
    // 以 AVUser 的用户名和密码登录即时通讯服务
    AV.User.logIn("username","password")
    .then(function(user){
    return realtime.createIMClient(user);
    })
    .catch(console.error.bind(console));

    // 定义一个常驻内存的全局变量
    var client:IMClient
    // 登录 User，然后使用登录成功的 User 初始化 Client 并登录
    LCUser.logIn(username:USER_NAME, password:PASSWORD){(result)in
    switch result {
    case.success(object:let user):
    do{
                client =tryIMClient(user: user)
                client.open{(result)in
    // handle result
    }
    }catch{
    print(error)
    }
    case.failure(error:let error):
    print(error)
    }
    }

    // 暂不支持

### 创建对话 `Conversation`

用户登录之后，要开始与其他人聊天，需要先创建一个「对话」。

对话（`Conversation`）是消息的载体，所有消息都是发送给对话，即时通讯服务端会把消息下发给所有在对话中的成员。

Tom 完成了登录之后，就可以选择用户聊天了。现在他要给 Jerry 发送消息，所以需要先创建一个只有他们两个成员的 `Conversation`：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var conversation =await tom.CreateConversation(newstring[]{"Jerry"},name:"Tom & Jerry",unique:true);

    tom.createConversation(Arrays.asList("Jerry"),"Tom & Jerry",null,false,true,
    newLCIMConversationCreatedCallback(){
    @Override
    publicvoiddone(LCIMConversation conversation,LCIMException e){
    if(e ==null){
    // 创建成功
    }
    }
    });

    // 创建与 Jerry 之间的对话
    [self createConversationWithClientIds:@[@"Jerry"] callback:^(LCIMConversation * _Nullable conversation, NSError * _Nullable error){
    // handle callback
    }];

    // 创建与 Jerry 之间的对话
    tom
    .createConversation({
    // tom 是一个 IMClient 实例
    // 指定对话的成员除了当前用户 Tom（SDK 会默认把当前用户当做对话成员）之外，还有 Jerry
    members:["Jerry"],
    // 对话名称
    name:"Tom & Jerry",
    unique:true,
    })
    .then(/* 略 */);

    do{
    try tom.createConversation(clientIDs:["Jerry"], name:"Tom & Jerry", isUnique:true, completion:{(result)in
    switch result {
    case.success(value:let conversation):
    print(conversation)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    // 创建与 Jerry 之间的对话
    Conversation conversation =await tom.createConversation(
          isUnique:true, members:{'Jerry'}, name:'Tom & Jerry');
    }catch(e){
    print('创建会话失败：$e');
    }

`createConversation` 这个接口会直接创建一个对话，并且该对话会被存储在 `_Conversation` 表内，可以打开 **开发者中心 > 你的游戏 > 游戏服务 > 云服务 > 数据存储 > 结构化数据** 查看数据。不同 SDK 提供的创建对话接口如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    /// <summary>
    /// Creates a conversation
    /// </summary>
    /// <param name="members">The list of clientIds of participants in this conversation (except the creator)</param>
    /// <param name="name">The name of this conversation</param>
    /// <param name="unique">Whether this conversation is unique;
    /// if it is true and an existing conversation contains the same composition of members,
    /// the existing conversation will be reused, otherwise a new conversation will be created.</param>
    /// <param name="properties">Custom attributes of this conversation</param>
    /// <returns></returns>
    publicasyncTask<LCIMConversation>CreateConversation(
    IEnumerable<string> members,
    string name =null,
    bool unique =true,
    Dictionary<string,object> properties =null){
    returnawait ConversationController.CreateConv(members: members,
    name: name,
    unique: unique,
    properties: properties);
    }

    /**
     * 创建或查询一个已有 conversation
     *
     * @param members 对话的成员
     * @param name 对话的名字
     * @param attributes 对话的额外属性
     * @param isTransient 是否是聊天室
     * @param isUnique 如果已经存在符合条件的会话，是否返回已有回话
     *                 为 false 时，则一直为创建新的回话
     *                 为 true 时，则先查询，如果已有符合条件的回话，则返回已有的，否则，创建新的并返回
     *                 为 true 时，仅 members 为有效查询条件
     * @param callback 结果回调函数
     */
    publicvoidcreateConversation(finalList<String> members,finalString name,
    finalMap<String,Object> attributes,finalboolean isTransient,finalboolean isUnique,
    finalLCIMConversationCreatedCallback callback);
    /**
     * 创建一个聊天对话
     *
     * @param members 对话参与者
     * @param attributes 对话的额外属性
     * @param isTransient 是否为聊天室
     * @param callback 结果回调函数
     */
    publicvoidcreateConversation(finalList<String> members,finalString name,
    finalMap<String,Object> attributes,finalboolean isTransient,
    finalLCIMConversationCreatedCallback callback);
    /**
     * 创建一个聊天对话
     *
     * @param conversationMembers 对话参与者
     * @param name       对话名称
     * @param attributes 对话属性
     * @param callback   结果回调函数
     * @since 3.0
     */
    publicvoidcreateConversation(finalList<String> conversationMembers,String name,
    finalMap<String,Object> attributes,finalLCIMConversationCreatedCallback callback);
    /**
     * 创建一个聊天对话
     *
     * @param conversationMembers 对话参与者
     * @param attributes 对话属性
     * @param callback   结果回调函数
     * @since 3.0
     */
    publicvoidcreateConversation(finalList<String> conversationMembers,
    finalMap<String,Object> attributes,finalLCIMConversationCreatedCallback callback);

    /// The option of conversation creation.
    @interface LCIMConversationCreationOption : NSObject
    /// The name of the conversation.
    @property(nonatomic, nullable) NSString *name;
    /// The attributes of the conversation.
    @property(nonatomic, nullable) NSDictionary *attributes;
    /// Create or get an unique conversation, default is `true`.
    @property(nonatomic) BOOL isUnique;
    /// The time interval for the life of the temporary conversation.
    @property(nonatomic) NSUInteger timeToLive;
    @end

    /// Create a Normal Conversation. Default is a Normal Unique Conversation.
    /// @param clientIds The set of client ID. it's the members of the conversation which will be created. the initialized members always contains the current client's ID. if the created conversation is unique, and the server has one unique conversation with the same members, that unique conversation will be returned.
    /// @param callback Result callback.
    -(void)createConversationWithClientIds:(NSArray<NSString *>*)clientIds
                                   callback:(void(^)(LCIMConversation * _Nullable conversation, NSError * _Nullable error))callback;

    /// Create a Normal Conversation. Default is a Normal Unique Conversation.
    /// @param clientIds The set of client ID. it's the members of the conversation which will be created. the initialized members always contains the current client's ID. if the created conversation is unique, and the server has one unique conversation with the same members, that unique conversation will be returned.
    /// @param option See `LCIMConversationCreationOption`.
    /// @param callback Result callback.
    -(void)createConversationWithClientIds:(NSArray<NSString *>*)clientIds
                                     option:(LCIMConversationCreationOption * _Nullable)option
                                   callback:(void(^)(LCIMConversation * _Nullable conversation, NSError * _Nullable error))callback;

    /// Create a Chat Room.
    /// @param callback Result callback.
    -(void)createChatRoomWithCallback:(void(^)(LCIMChatRoom * _Nullable chatRoom, NSError * _Nullable error))callback;

    /// Create a Chat Room.
    /// @param option See `LCIMConversationCreationOption`.
    /// @param callback Result callback.
    -(void)createChatRoomWithOption:(LCIMConversationCreationOption * _Nullable)option
                            callback:(void(^)(LCIMChatRoom * _Nullable chatRoom, NSError * _Nullable error))callback;

    /// Create a Temporary Conversation. Temporary Conversation is unique in its Life Cycle.
    /// @param clientIds The set of client ID. it's the members of the conversation which will be created. the initialized members always contains this client's ID.
    /// @param callback Result callback.
    -(void)createTemporaryConversationWithClientIds:(NSArray<NSString *>*)clientIds
                                            callback:(void(^)(LCIMTemporaryConversation * _Nullable temporaryConversation, NSError * _Nullable error))callback;

    /// Create a Temporary Conversation. Temporary Conversation is unique in its Life Cycle.
    /// @param clientIds The set of client ID. it's the members of the conversation which will be created. the initialized members always contains this client's ID.
    /// @param option See `LCIMConversationCreationOption`.
    /// @param callback Result callback.
    -(void)createTemporaryConversationWithClientIds:(NSArray<NSString *>*)clientIds
                                              option:(LCIMConversationCreationOption * _Nullable)option
                                            callback:(void(^)(LCIMTemporaryConversation * _Nullable temporaryConversation, NSError * _Nullable error))callback;

    /**
     * 创建一个对话
     * @param {Object} options 除了下列字段外的其他字段将被视为对话的自定义属性
     * @param {String[]} options.members 对话的初始成员列表，必要参数，默认包含当前 client
     * @param {String} [options.name] 对话的名字，可选参数，如果不传默认值为 null
     * @param {Boolean} [options.transient=false] 是否为聊天室，可选参数
     * @param {Boolean} [options.unique=false] 是否唯一对话，当其为 true 时，如果当前已经有相同成员的对话存在则返回该对话，否则会创建新的对话
     * @param {Boolean} [options.tempConv=false] 是否为临时对话，可选参数
     * @param {Integer} [options.tempConvTTL=0] 可选参数，如果 tempConv 为 true，这里可以指定临时对话的生命周期。
     * @return {Promise.<Conversation>}
     */
    asynccreateConversation({
    members: m,
        name,
        transient,
        unique,
        tempConv,
        tempConvTTL,
    // 可添加更多属性
    });

    /// Create a Normal Conversation. Default is a Unique Conversation.
    ///
    /// - Parameters:
    ///   - clientIDs: The set of client ID. it's the members of the conversation which will be created. the initialized members always contains the current client's ID. if the created conversation is unique, and the server has one unique conversation with the same members, that unique conversation will be returned.
    ///   - name: The name of the conversation.
    ///   - attributes: The attributes of the conversation.
    ///   - isUnique: True means create or get a unique conversation, default is true.
    ///   - completion: callback.
    publicfunccreateConversation(clientIDs:Set<String>, name:String?=nil, attributes:[String:Any]?=nil, isUnique:Bool=true, completion:@escaping(LCGenericResult<IMConversation>)->Void)throws

    /// Create a Chat Room.
    ///
    /// - Parameters:
    ///   - name: The name of the chat room.
    ///   - attributes: The attributes of the chat room.
    ///   - completion: callback.
    publicfunccreateChatRoom(name:String?=nil, attributes:[String:Any]?=nil, completion:@escaping(LCGenericResult<IMChatRoom>)->Void)throws

    /// Create a Temporary Conversation. Temporary Conversation is unique in its Life Cycle.
    ///
    /// - Parameters:
    ///   - clientIDs: The set of client ID. it's the members of the conversation which will be created. the initialized members always contains this client's ID.
    ///   - timeToLive: The time interval for the life of the temporary conversation.
    ///   - completion: callback.
    publicfunccreateTemporaryConversation(clientIDs:Set<String>, timeToLive:Int32, completion:@escaping(LCGenericResult<IMTemporaryConversation>)->Void)throws

    /// To create a normal [Conversation].
    ///
    /// [isUnique] is a special parameter, default is `true`, it affects the creation behavior and property [Conversation.isUnique].
    ///   * When it is `true` and the relevant unique [Conversation] not exists in the server, this method will create a new unique [Conversation].
    ///   * When it is `true` and the relevant unique [Conversation] exists in the server, this method will return that existing unique [Conversation].
    ///   * When it is `false`, this method always create a new non-unique [Conversation].
    ///
    /// [members] is the [Conversation.members].
    /// [name] is the [Conversation.name].
    /// [attributes] is the [Conversation.attributes].
    ///
    /// Returns an instance of [Conversation].
    Future<Conversation>createConversation({
      bool isUnique =true,
    Set<String> members,
    String name,
    Map<String,dynamic> attributes,
    })async{}

    /// To create a new [ChatRoom].
    ///
    /// [name] is the [Conversation.name].
    /// [attributes] is the [Conversation.attributes].
    ///
    /// Returns an instance of [ChatRoom].
    Future<ChatRoom>createChatRoom({
    String name,
    Map<String,dynamic> attributes,
    })async{}

    /// To create a new [TemporaryConversation].
    ///
    /// [members] is the [Conversation.members].
    /// [timeToLive] is the [TemporaryConversation.timeToLive].
    ///
    /// Returns an instance of [TemporaryConversation].
    Future<TemporaryConversation>createTemporaryConversation({
    Set<String> members,
      int timeToLive,
    })async{}

虽然不同语言／平台接口声明有所不同，但是支持的参数是基本一致的。在创建一个对话的时候，我们主要可以指定：

  1. `members`：必要参数，包含对话的初始成员列表，请注意当前用户作为对话的创建者，是默认包含在成员里面的，所以 `members` 数组中可以不包含当前用户的 `clientId`。

  2. `name`：对话名字，可选参数，上面代码指定为了「Tom & Jerry」。

  3. `attributes`：对话的自定义属性，可选。上面示例代码没有指定额外属性，开发者如果指定了额外属性的话，以后其他成员可以通过 `LCIMConversation` 的接口获取到这些属性值。附加属性在 `_Conversation` 表中被保存在 `attr` 列中。

  4. `unique`/`isUnique` 或者是 `LCIMConversationOptionUnique`：唯一对话标志位，可选。

     * 如果设置为唯一对话，云端会根据完整的成员列表先进行一次查询，如果已经有正好包含这些成员的对话存在，那么就返回已经存在的对话，否则才创建一个新的对话。
     * 如果指定 `unique` 标志为假，那么每次调用 `createConversation` 接口都会创建一个新的对话。
     * 未指定 `unique` 时，SDK 默认值为真。
     * 从通用的聊天场景来看，不管是 Tom 发出「创建和 Jerry 单聊对话」的请求，还是 Jerry 发出「创建和 Tom 单聊对话」的请求，或者 Tom 以后再次发出创建和 Jerry 单聊对话的请求，都应该是同一个对话才是合理的，否则可能因为聊天记录的不同导致用户混乱。
  5. 对话类型的其他标志，可选参数，例如 `transient`/`isTransient` 表示「聊天室」，`tempConv`/`tempConvTTL` 和 `LCIMConversationOptionTemporary` 用来创建「临时对话」等等。什么都不指定就表示创建普通对话，对于这些标志位的含义我们先不管，以后会有说明。

创建对话之后，可以获取对话的内置属性，云端会为每一个对话生成一个全局唯一的 ID 属性：`Conversation.id`，它是其他用户查询对话时常用的匹配字段。

### 发送消息

对话已经创建成功了，接下来 Tom 可以在这个对话中发出第一条文本消息了：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var textMessage =newLCIMTextMessage("Jerry，起床了！");
    await conversation.Send(textMessage);

    LCIMTextMessage msg =newLCIMTextMessage();
    msg.setText("Jerry，起床了！");
    // 发送消息
    conversation.sendMessage(msg,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    Log.d("Tom & Jerry","发送成功！");
    }
    }
    });

    LCIMTextMessage *message =[LCIMTextMessage messageWithText:@"耗子，起床！" attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    var{TextMessage}=require("leancloud-realtime");
    conversation
    .send(newTextMessage("Jerry，起床了！"))
    .then(function(message){
    console.log("Tom & Jerry","发送成功！");
    })
    .catch(console.error);

    do{
    let textMessage =IMTextMessage(text:"Jerry，起床了！")
    try conversation.send(message: textMessage){(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    try{
    TextMessage textMessage =TextMessage();
      textMessage.text ='Jerry，起床了！';
    await conversation.send(message: textMessage);
    }catch(e){
    print(e);
    }

上面接口实现的功能就是向对话中发送一条消息，同一对话中其他在线成员会立刻收到此消息。

现在 Tom 发出了消息，那么接收者 Jerry 他要在界面上展示出来这一条新消息，该怎么来处理呢？

### 接收消息

在另一个设备上，我们用 `Jerry` 作为 `clientId` 来创建一个 `IMClient` 并登录即时通讯服务（与前两节 Tom 的处理流程一样）：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var jerry =newLCIMClient("Jerry");

    // Jerry 登录
    LCIMClient jerry =LCIMClient.getInstance("Jerry");
    jerry.open(newLCIMClientCallback(){
    @Override
    publicvoiddone(LCIMClient client,LCIMException e){
    if(e==null){
    // 登录成功后的逻辑
    }
    }
    });

    NSError *error;
    jerry =[[LCIMClient alloc] initWithClientId:@"Jerry" error:&error];
    if(!error){
    [jerry openWithCallback:^(BOOL succeeded, NSError *error){
    // handle callback
    }];
    }

    var{Event}=require("leancloud-realtime");
    // Jerry 登录
    realtime
    .createIMClient("Jerry")
    .then(function(jerry){})
    .catch(console.error);

    do{
    let jerry =tryIMClient(ID:"Jerry")
        jerry.open{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    Client jerry =Client(id:'Jerry');
    await jerry.open();

Jerry 作为消息的被动接收方，他不需要主动创建与 Tom 的对话，可能也无法知道 Tom 创建好的对话信息，Jerry 端需要通过设置即时通讯客户端事件的回调函数，才能获取到 Tom 那边操作的通知。

即时通讯客户端事件回调能处理多种服务端通知，这里我们先关注这里会出现的两个事件：

* 用户被邀请进入某个对话的通知事件。Tom 在创建和 Jerry 的单聊对话的时候，Jerry 这边就能立刻收到一条通知，获知到类似于「Tom 邀请你加入了一个对话」的信息。
* 已加入对话中新消息到达的通知。在 Tom 发出「Jerry，起床了！」这条消息之后，Jerry 这边也能立刻收到一条新消息到达的通知，通知中带有消息具体数据以及对话、发送者等上下文信息。

现在，我们看看具体应该如何响应服务端发过来的通知。Jerry 端会分别处理「加入对话」的事件通知和「新消息到达」的事件通知：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    jerry.OnInvited =(conv, initBy)=>{
    WriteLine($"{initBy} 邀请 Jerry 加入 {conv.Id} 对话");
    };
    jerry.OnMessage =(conv, msg)=>{
    if(msg isLCIMTextMessage textMessage){
    // textMessage.ConversationId 是该条消息所属于的对话 ID
    // textMessage.Text 是该文本消息的文本内容
    // textMessage.FromClientId 是消息发送者的 clientId
    }
    };

    // Java/Android SDK 通过定制自己的对话事件 Handler 处理服务端下发的对话事件通知
    publicclassCustomConversationEventHandlerextendsLCIMConversationEventHandler{
    /**
       * 实现本方法来处理当前用户被邀请到某个聊天对话事件
          *
       * @param client
       * @param conversation 被邀请的聊天对话
       * @param operator 邀请你的人
       * @since 3.0
          */
    @Override
    publicvoidonInvited(LCIMClient client,LCIMConversation conversation,String invitedBy){
    // 当前 clientId（Jerry）被邀请到对话，执行此处逻辑
    }
    }
    // 设置全局的对话事件处理 handler
    LCIMMessageManager.setConversationEventHandler(newCustomConversationEventHandler());

    // Java/Android SDK 通过定制自己的消息事件 Handler 处理服务端下发的消息通知
    publicstaticclassCustomMessageHandlerextendsLCIMMessageHandler{
    /**
       * 重载此方法来处理接收消息
          *
       * @param message
       * @param conversation
       * @param client
          */
    @Override
    publicvoidonMessage(LCIMMessage message,LCIMConversation conversation,LCIMClient client){
    if(message instanceofLCIMTextMessage){
    Log.d(((LCIMTextMessage)message).getText());// Jerry，起床了
    }
    }
    }
    // 设置全局的消息处理 handler
    LCIMMessageManager.registerDefaultMessageHandler(newCustomMessageHandler());

    // Objective-C SDK 通过实现 LCIMClientDelegate 代理来处理服务端通知
    // 不了解 Objective-C 代理（delegate）概念的读者可以参考：
    // https://developer.apple.com/library/archive/documentation/General/Conceptual/CocoaEncyclopedia/DelegatesandDataSources/DelegatesandDataSources.html
    jerry.delegate = delegator;

    /*!
     当前用户被邀请加入对话的通知。
     @param conversation － 所属对话
     @param clientId - 邀请者的 ID
     */
    -(void)conversation:(LCIMConversation *)conversation invitedByClientId:(NSString *)clientId {
    NSLog(@"%@",[NSString stringWithFormat:@"当前 clientId（Jerry）被 %@ 邀请，加入了对话",clientId]);
    }

    /*!
     接收到新消息（使用内置消息格式）。
     @param conversation － 所属对话
     @param message - 具体的消息
     */
    -(void)conversation:(LCIMConversation *)conversation didReceiveTypedMessage:(LCIMTypedMessage *)message {
    NSLog(@"%@", message.text);// Jerry，起床了！
    }

    // JS SDK 通过在 IMClient 实例上监听事件回调来响应服务端通知

    // 当前用户被添加至某个对话
    jerry.on(Event.INVITED,functioninvitedEventHandler(payload, conversation){
    console.log(payload.invitedBy, conversation.id);
    });

    // 当前用户收到了某一条消息，可以通过响应 Event.MESSAGE 这一事件来处理。
    jerry.on(Event.MESSAGE,function(message, conversation){
    console.log("收到新消息："+ message.text);
    });

    let delegator:Delegator=Delegator()
    jerry.delegate = delegator

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    case.message(event:let messageEvent):
    switch messageEvent {
    case.received(message:let message):
    print(message)
    default:
    break
    }
    default:
    break
    }
    }

    jerry.onMessage =({
    Client client,
    Conversation conversation,
    Message message,
    }){
    if(message.stringContent !=null){
    print('收到的消息是：${message.stringContent}');
    }
    };

Jerry 端实现了上面两个事件通知函数之后，就顺利收到 Tom 发送的消息了。之后 Jerry 也可以回复消息给 Tom，而 Tom 端实现类似的接收流程，那么他们俩就可以开始愉快的聊天了。

我们现在可以回顾一下 Tom 和 Jerry 发送第一条消息的过程中，两方完整的处理时序：

sequenceDiagram Tom->>Cloud: 1. Tom 将 Jerry 加入对话 Cloud-->>Jerry: 2. 下发通知：你被邀请加入对话 Jerry-->>UI: 3. 加载聊天的 UI 界面 Tom->>Cloud: 4. 发送消息 Cloud-->>Jerry: 5. 下发通知：接收到有新消息 Jerry-->>UI: 6. 显示收到的消息内容

在聊天过程中，接收方除了响应新消息到达通知之外，还需要响应多种对话成员变动通知，例如「新用户 XX 被 XX 邀请加入了对话」、「用户 XX 主动退出了对话」、「用户 XX 被管理员剔除出对话」，等等。 云端会实时下发这些事件通知给客户端，具体细节可以参考后续章节：[成员变更的事件通知总结](#%E6%88%90%E5%91%98%E5%8F%98%E6%9B%B4%E7%9A%84%E4%BA%8B%E4%BB%B6%E9%80%9A%E7%9F%A5%E6%80%BB%E7%BB%93)。

## 多人群聊

上面我们讨论了一对一单聊的实现流程，假设我们还需要实现一个「朋友群」的多人聊天，接下来我们就看看怎么完成这一功能。

从即时通讯云端来看，多人群聊与单聊的流程十分接近，主要差别在于对话内成员数量的多少。群聊对话支持在创建对话的时候一次性指定全部成员，也允许在创建之后通过邀请的方式来增加新的成员。

### 创建多人群聊对话

在 Tom 和 Jerry 的对话中（假设对话 ID 为 `CONVERSATION_ID`，这只是一个示例，并不代表实际数据），后来 Tom 又希望把 Mary 也拉进来，他可以使用如下的办法：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // 首先根据 ID 获取 Conversation 实例
    var conversation =await tom.GetConversation("CONVERSATION_ID");
    // 邀请 Mary 加入对话
    await conversation.AddMembers(newstring[]{"Mary"});

    // 首先根据 ID 获取 Conversation 实例
    finalLCIMConversation conv = client.getConversation("CONVERSATION_ID");
    // 邀请 Mary 加入对话
    conv.addMembers(Arrays.asList("Mary"),newLCIMOperationPartiallySucceededCallback(){
    @Override
    publicvoiddone(LCIMException e,List<String> successfulClientIds,List<LCIMOperationFailure> failures){
    // 添加成功
    }
    });

    // 首先根据 ID 获取 Conversation 实例
    LCIMConversationQuery *query =[self.client conversationQuery];
    [query getConversationById:@"CONVERSATION_ID" callback:^(LCIMConversation *conversation, NSError *error){
    // 邀请 Mary 加入对话
    [conversation addMembersWithClientIds:@[@"Mary"] callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"邀请成功！");
    }
    }];
    }];

    // 首先根据 ID 获取 Conversation 实例
    tom
    .getConversation("CONVERSATION_ID")
    .then(function(conversation){
    // 邀请 Mary 加入对话
    return conversation.add(["Mary"]);
    })
    .then(function(conversation){
    console.log("添加成功", conversation.members);
    // 此时对话成员为：['Mary', 'Tom', 'Jerry']
    })
    .catch(console.error.bind(console));

    do{
    let conversationQuery = client.conversationQuery
    try conversationQuery.getConversation(by:"CONVERSATION_ID"){(result)in
    switch result {
    case.success(value:let conversation):
    do{
    try conversation.add(members:["Mary"], completion:{(result)in
    switch result {
    case.allSucceeded:
    break
                        case.failure(error:let error):
    print(error)
    caselet.slicing(success: succeededIDs, failure: failures):
    iflet succeededIDs = succeededIDs {
    print(succeededIDs)
    }
    for(failedIDs, error)in failures {
    print(failedIDs)
    print(error)
    }
    }
    })
    }catch{
    print(error)
    }
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    List<Conversation> conversations;
    try{
    // 首先根据 ID 获取 Conversation 实例
    ConversationQuery query = tom.conversationQuery();
      query.whereEqualTo('objectId','CONVERSATION_ID');
      conversations =await query.find();
    }catch(e){
    print(e);
    }
    try{
    Conversation conversation = conversations.first;
    // 邀请 Mary 加入对话
    MemberResult addResult =await conversation.addMembers(
        members:{'Mary'},
    );
    }catch(e){
    print(e);
    }

而 Jerry 端增加「新成员加入」的事件通知处理函数，就可以及时获知 Mary 被 Tom 邀请加入当前对话了：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    jerry.OnMembersJoined =(conv, memberList, initBy)=>{
    WriteLine($"{initBy} 邀请了 {memberList} 加入了 {conv.Id} 对话");
    }

其中 `AVIMOnInvitedEventArgs` 参数包含如下内容：

  1. `InvitedBy`：该操作的发起者
  2. `JoinedMembers`：此次加入对话的包含的成员列表
  3. `ConversationId`：被操作的对话

    publicclassCustomConversationEventHandlerextendsLCIMConversationEventHandler{
    /**
       * 实现本方法以处理聊天对话中的参与者加入事件
       *
       * @param client
       * @param conversation
       * @param members 加入的参与者
       * @param invitedBy 加入事件的邀请人，有可能是加入的参与者本身
       * @since 3.0
       */
    @Override
    publicvoidonMemberJoined(LCIMClient client,LCIMConversation conversation,
    List<String> members,String invitedBy){
    // 手机屏幕上会显示一小段文字：Mary 加入到 551260efe4b01608686c3e0f；操作者为：Tom
    Toast.makeText(LeanCloud.applicationContext,
              members +" 加入到 "+ conversation.getConversationId()+"；操作者为："
    + invitedBy,Toast.LENGTH_SHORT).show();
    }
    }
    // 设置全局的对话事件处理 handler
    LCIMMessageManager.setConversationEventHandler(newCustomConversationEventHandler());

    jerry.delegate = delegator;

    #pragmamark - LCIMClientDelegate
    /*!
     对话中有新成员加入时所有成员都会收到这一通知。
     @param conversation － 所属对话
     @param clientIds - 加入的新成员列表
     @param clientId - 邀请者的 ID
     */
    -(void)conversation:(LCIMConversation *)conversation membersAdded:(NSArray *)clientIds byClientId:(NSString *)clientId {
    NSLog(@"%@",[NSString stringWithFormat:@"%@ 加入到对话，操作者为：%@",[clientIds objectAtIndex:0],clientId]);
    }

    // 有用户被添加至某个对话
    jerry.on(
    Event.MEMBERS_JOINED,
    functionmembersjoinedEventHandler(payload, conversation){
    console.log(payload.members, payload.invitedBy, conversation.id);
    }
    );

其中 `payload` 参数包含如下内容：

  1. `members`：字符串数组，被添加的用户 `clientId` 列表
  2. `invitedBy`：字符串，邀请者 `clientId`

    jerry.delegate = delegator

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    caselet.joined(byClientID: byClientID, at: atDate):
    print(byClientID)
    print(atDate)
    caselet.membersJoined(members: members, byClientID: byClientID, at: atDate):
    print(members)
    print(byClientID)
    print(atDate)
    default:
    break
    }
    }

    // 加入成员通知
    jerry.onMembersJoined =({
    Client client,
    Conversation conversation,
    List members,
    String byClientID,
    DateTime atDate,
    }){
    print('成员 ${members.toString()} 加入会话');
    };

这一流程的时序图如下：

sequenceDiagram Tom->>Cloud: 1. 添加 Mary Cloud->>Tom: 2. 下发通知：Mary 被你邀请加入了对话 Cloud-->>Mary: 2. 下发通知：你被 Tom 邀请加入对话 Cloud-->>Jerry: 2. 下发通知：Mary 被 Tom 邀请加入了对话

而 Mary 端如果要能加入到 Tom 和 Jerry 的对话中来，Ta 可以参照 [一对一单聊](#%E4%B8%80%E5%AF%B9%E4%B8%80%E5%8D%95%E8%81%8A) 中 Jerry 侧的做法监听 `INVITED` 事件，就可以自己被邀请到了一个对话当中。

而 **重新创建一个对话，并在创建的时候指定全部成员** 的方式如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var conversation =await tom.CreateConversation(newstring[]{"Jerry","Mary"},name:"Tom & Jerry & friends",unique:true);

    tom.createConversation(Arrays.asList("Jerry","Mary"),"Tom & Jerry & friends",null,
    newLCIMConversationCreatedCallback(){
    @Override
    publicvoiddone(LCIMConversation conversation,LCIMException e){
    if(e ==null){
    // 创建成功
    }
    }
    });

    // Tom 建立了与朋友们的会话
    [tom createConversationWithClientIds:@[@"Jerry",@"Mary"] callback:^(LCIMConversation * _Nullable conversation, NSError * _Nullable error){
    if(!error){
    NSLog(@"创建成功！");
    }
    }];

    tom
    .createConversation({
    // 创建的时候直接指定 Jerry 和 Mary 一起加入多人群聊，当然根据需求可以添加更多成员
    members:["Jerry","Mary"],
    // 对话名称
    name:"Tom & Jerry & friends",
    unique:true,
    })
    .catch(console.error);

    do{
    try tom.createConversation(clientIDs:["Jerry","Mary"], name:"Tom & Jerry & friends", isUnique:true, completion:{(result)in
    switch result {
    case.success(value:let conversation):
    print(conversation)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    Conversation conversation =await jerry.createConversation(
          isUnique:true,
          members:{'Jerry','Mary'},
          name:'Tom & Jerry & friends');
    }catch(e){
    print(e);
    }

### 群发消息

多人群聊中一个成员发送的消息，会实时同步到所有其他在线成员，其处理流程与单聊中 Jerry 接收消息的过程是一样的。

例如，Tom 向好友群发送了一条欢迎消息：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var textMessage =newLCIMTextMessage("大家好，欢迎来到我们的群聊对话！");
    await conversation.Send(textMessage);

    LCIMTextMessage msg =newLCIMTextMessage();
    msg.setText("大家好，欢迎来到我们的群聊对话！");
    // 发送消息
    conversation.sendMessage(msg,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    Log.d("群聊","发送成功！");
    }
    }
    });

    [conversation sendMessage:[LCIMTextMessage messageWithText:@"大家好，欢迎来到我们的群聊对话！" attributes:nil] callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    conversation.send(newTextMessage("大家好，欢迎来到我们的群聊对话"));

    do{
    let textMessage =IMTextMessage(text:"大家好，欢迎来到我们的群聊对话！")
    try conversation.send(message: textMessage, completion:{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    TextMessage textMessage =TextMessage();
      textMessage.text ='大家好，欢迎来到我们的群聊对话！';
    await conversation.send(message: textMessage);
    }catch(e){
    print(e);
    }

而 Jerry 和 Mary 端都会有 `Event.MESSAGE` 事件触发，利用它来接收群聊消息，并更新产品 UI。

### 将他人踢出对话

三个好友的群其乐融融不久，后来 Mary 出言不逊，惹恼了群主 Tom，Tom 直接把 Mary 踢出了对话群。Tom 端想要踢人，该怎么实现呢？

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await conversation.RemoveMembers(newstring[]{"Mary"});

    conv.kickMembers(Arrays.asList("Mary"),newLCIMOperationPartiallySucceededCallback(){
    @Override
    publicvoiddone(LCIMException e,List<String> successfulClientIds,List<LCIMOperationFailure> failures){
    }
    });

    [conversation removeMembersWithClientIds:@[@"Mary"] callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"踢人成功！");
    }
    }];

    conversation
    .remove(["Mary"])
    .then(function(conversation){
    console.log("移除成功", conversation.members);
    })
    .catch(console.error.bind(console));

    do{
    try conversation.remove(members:["Mary"], completion:{(result)in
    switch result {
    case.allSucceeded:
    break
            case.failure(error:let error):
    print(error)
    caselet.slicing(success: succeededIDs, failure: failures):
    iflet succeededIDs = succeededIDs {
    print(succeededIDs)
    }
    for(failedIDs, error)in failures {
    print(failedIDs)
    print(error)
    }
    }
    })
    }catch{
    print(error)
    }

    try{
    MemberResult removeMemberResult =await conversation.removeMembers(members:{'Mary'});
    }catch(e){
    print(e);
    }

Tom 端执行了这段代码之后会触发如下流程：

sequenceDiagram Tom->>Cloud: 1. 对话中移除 Mary Cloud-->>Mary: 2. 下发通知：你被 Tom 从对话中剔除了 Cloud-->>Jerry: 2. 下发通知：Mary 被 Tom 移除 Cloud-->>Tom: 2. 下发通知：Mary 被移除了对话

这里出现了两个新的事件：当前用户被踢出对话 `KICKED`（Mary 收到的），成员 XX 被踢出对话 `MEMBERS_LEFT`（Jerry 和 Tom 收到的）。其处理方式与邀请人的流程类似：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    jerry.OnMembersLeft =(conv, leftIds, kickedBy)=>{
    WriteLine($"{leftIds} 离开对话 {conv.Id}；操作者为：{kickedBy}");
    }
    jerry.OnKicked =(conv, initBy)=>{
    WriteLine($"你已经离开对话 {conv.Id}；操作者为：{initBy}");
    };

    publicclassCustomConversationEventHandlerextendsLCIMConversationEventHandler{
    /**
       * 实现本方法以处理聊天对话中的参与者离开事件
          *
       * @param client
       * @param conversation
       * @param members 离开的参与者
       * @param kickedBy 离开事件的发动者，有可能是离开的参与者本身
       * @since 3.0
          */
    @Override
    publicabstractvoidonMemberLeft(LCIMClient client,
    LCIMConversation conversation,List<String> members,String kickedBy){
    Toast.makeText(LeanCloud.applicationContext,
          members +" 离开对话 "+ conversation.getConversationId()+"；操作者为："
    + kickedBy,Toast.LENGTH_SHORT).show();
    }
    /**
       * 实现本方法来处理当前用户被踢出某个聊天对话事件
       *
       * @param client
       * @param conversation
       * @param kickedBy 踢出你的人
       * @since 3.0
       */
    @Override
    publicabstractvoidonKicked(LCIMClient client,LCIMConversation conversation,
    String kickedBy){
    Toast.makeText(LeanCloud.applicationContext,
    "你已离开对话 "+ conversation.getConversationId()+"；操作者为："
    + kickedBy,Toast.LENGTH_SHORT).show();
    }
    }
    // 设置全局的对话事件处理 handler
    LCIMMessageManager.setConversationEventHandler(newCustomConversationEventHandler());

    jerry.delegate = delegator;

    #pragmamark - LCIMClientDelegate
    /*!
     对话中有成员离开时所有剩余成员都会收到这一通知。
     @param conversation － 所属对话
     @param clientIds - 离开的成员列表
     @param clientId - 操作者的 ID
     */
    -(void)conversation:(LCIMConversation *)conversation membersRemoved:(NSArray<NSString *>* _Nullable)clientIds byClientId:(NSString * _Nullable)clientId {
    ;
    }
    /*!
     当前用户被踢出对话的通知。
     @param conversation － 所属对话
     @param clientId - 操作者的 ID
     */
    -(void)conversation:(LCIMConversation *)conversation kickedByClientId:(NSString * _Nullable)clientId {
    ;
    }

    // 有成员被从某个对话中移除
    jerry.on(
    Event.MEMBERS_LEFT,
    functionmembersjoinedEventHandler(payload, conversation){
    console.log(payload.members, payload.kickedBy, conversation.id);
    }
    );
    // 有用户被踢出某个对话
    jerry.on(
    Event.KICKED,
    functionmembersjoinedEventHandler(payload, conversation){
    console.log(payload.kickedBy, conversation.id);
    }
    );

    jerry.delegate = delegator

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    caselet.left(byClientID: byClientID, at: atDate):
    print(byClientID)
    print(atDate)
    caselet.membersLeft(members: members, byClientID: byClientID, at: atDate):
    print(members)
    print(byClientID)
    print(atDate)
    default:
    break
    }
    }

    // 有成员被从某个对话中移除
    jerry.onMembersLeft =({
    Client client,
    Conversation conversation,
    List members,
    String byClientID,
    DateTime atDate,
    }){
    print('成员 ${members.toString()} 离开会话，操作者为：$byClientID');
    };
    // 有用户被踢出某个对话
    jerry.onKicked =({
    Client client,
    Conversation conversation,
    String byClientID,
    DateTime atDate,
    }){
    print('你已离开对话，操作者为：$byClientID');
    };

### 用户主动加入对话

把 Mary 踢走之后，Tom 嫌人少不好玩，所以他找到了 William，说他和 Jerry 有一个很好玩的聊天群，并且把群的 ID（或名称）告知给了 William。William 也很想进入这个群看看他们究竟在聊什么，他自己主动加入了对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var conv =await william.GetConversation("CONVERSATION_ID");
    await conv.Join();

    LCIMConversation conv = william.getConversation("CONVERSATION_ID");
    conv.join(newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e==null){
    // 加入成功
    }
    }
    });

    LCIMConversationQuery *query =[william conversationQuery];
    [query getConversationById:@"CONVERSATION_ID" callback:^(LCIMConversation *conversation, NSError *error){
    [conversation joinWithCallback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"加入成功！");
    }
    }];
    }];

    william
    .getConversation("CONVERSATION_ID")
    .then(function(conversation){
    return conversation.join();
    })
    .then(function(conversation){
    console.log("加入成功", conversation.members);
    // 此时对话成员为：['William', 'Tom', 'Jerry']
    })
    .catch(console.error.bind(console));

    do{
    let conversationQuery = client.conversationQuery
    try conversationQuery.getConversation(by:"CONVERSATION_ID"){(result)in
    switch result {
    case.success(value:let conversation):
    do{
    try conversation.join(completion:{(result)in
    switch result {
    case.success:
    break
                        case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    List<Conversation> conversations;
    try{
    ConversationQuery query = william.conversationQuery();
      query.whereEqualTo('objectId','CONVERSATION_ID');
      conversations =await query.find();
    }catch(e){
    print(e);
    }

    try{
    Conversation conversation = conversations.first;
    MemberResult joinResult =await conversation.join();
    }catch(e){
    print(e);
    }

执行了这段代码之后会触发如下流程：

sequenceDiagram William->>Cloud: 1. 加入对话 Cloud-->>William: 2. 下发通知：你已加入对话 Cloud-->>Tom: 2. 下发通知：William 加入对话 Cloud-->>Jerry: 2. 下发通知：William 加入对话

其他人则通过订阅 `MEMBERS_JOINED` 来接收 William 加入对话的通知 :

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    jerry.OnMembersJoined =(conv, memberList, initBy)=>{
    WriteLine($"{memberList} 加入了 {conv.Id} 对话；操作者为：{initBy}");
    }

    publicclassCustomConversationEventHandlerextendsLCIMConversationEventHandler{
    @Override
    publicvoidonMemberJoined(LCIMClient client,LCIMConversation conversation,
    List<String> members,String invitedBy){
    // 手机屏幕上会显示一小段文字：William 加入到 551260efe4b01608686c3e0f；操作者为：William
    Toast.makeText(LeanCloud.applicationContext,
            members +" 加入到 "+ conversation.getConversationId()+"；操作者为："
    + invitedBy,Toast.LENGTH_SHORT).show();
    }
    }

    -(void)conversation:(LCIMConversation *)conversation membersAdded:(NSArray *)clientIds byClientId:(NSString *)clientId {
    NSLog(@"%@",[NSString stringWithFormat:@"%@ 加入到对话，操作者为：%@",[clientIds objectAtIndex:0],clientId]);
    }

    jerry.on(
    Event.MEMBERS_JOINED,
    functionmembersJoinedEventHandler(payload, conversation){
    console.log(payload.members, payload.invitedBy, conversation.id);
    }
    );

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    caselet.membersJoined(members: members, byClientID: byClientID, at: atDate):
    print(members)
    print(byClientID)
    print(atDate)
    default:
    break
    }
    }

    jerry.onMembersJoined =({
    Client client,
    Conversation conversation,
    List members,
    String byClientID,
    DateTime atDate,
    }){
    print('成员 ${members.toString()} 加入会话');
    };

### 用户主动退出对话

随着 Tom 邀请进来的人越来越多，Jerry 觉得跟这些人都说不到一块去，他不想继续呆在这个对话里面了，所以选择自己主动退出对话，这时候可以调用下面的方法完成退群的操作：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await conversation.Quit();

    conversation.quit(newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e==null){
    // 退出成功
    }
    }
    });

    [conversation quitWithCallback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"退出成功！");
    }
    }];

    conversation
    .quit()
    .then(function(conversation){
    console.log("退出成功", conversation.members);
    })
    .catch(console.error.bind(console));

    do{
    try conversation.leave(completion:{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    MemberResult quitResult =await conversation.quit();
    }catch(e){
    print(e);
    }

执行了这段代码 Jerry 就离开了这个聊天群，此后群里所有的事件 Jerry 都不会再知晓。各个成员接收到的事件通知流程如下：

sequenceDiagram Jerry->>Cloud: 1. 离开对话 Cloud-->>Jerry: 2. 下发通知：你已离开对话 Cloud-->>Mary: 2. 下发通知：Jerry 已离开对话 Cloud-->>Tom: 2. 下发通知：Jerry 已离开对话

而其他人需要通过订阅 `MEMBERS_LEFT` 来接收 Jerry 离开对话的事件通知：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    mary.OnMembersLeft =(conv, members, initBy)=>{
    WriteLine($"{members} 离开了 {conv.Id} 对话；操作者为：{initBy}");
    }

    publicclassCustomConversationEventHandlerextendsLCIMConversationEventHandler{
    @Override
    publicvoidonMemberLeft(LCIMClient client,LCIMConversation conversation,List<String> members,
    String kickedBy){
    // 有其他成员离开时，执行此处逻辑
    }
    }

    // Mary 登录之后，Jerry 退出了对话，在 Mary 所在的客户端就会激发以下回调
    -(void)conversation:(LCIMConversation *)conversation membersRemoved:(NSArray *)clientIds byClientId:(NSString *)clientId {
    NSLog(@"%@",[NSString stringWithFormat:@"%@ 离开了对话，操作者为：%@",[clientIds objectAtIndex:0],clientId]);
    }

    mary.on(
    Event.MEMBERS_LEFT,
    functionmembersLeftEventHandler(payload, conversation){
    console.log(payload.members, payload.kickedBy, conversation.id);
    }
    );

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    caselet.membersLeft(members: members, byClientID: byClientID, at: atDate):
    print(members)
    print(byClientID)
    print(atDate)
    default:
    break
    }
    }

    mary.onMembersLeft =({
    Client client,
    Conversation conversation,
    List members,
    String byClientID,
    DateTime atDate,
    }){
    print('成员 ${members.toString()} 离开会话');
    };

### 成员变更的事件通知总结

前面的时序图和代码针对成员变更的操作做了逐步的分析和阐述，为了确保开发者能够准确的使用事件通知，如下表格做了一个统一的归类和划分：

假设 Tom 和 Jerry 已经在对话内了：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

| 操作 | Tom | Jerry | Mary | William |
| --- | --- | --- | --- | --- |
| Tom 添加 Mary | `OnMembersJoined` | `OnMembersJoined` | `OnInvited` | / |
| Tom 剔除 Mary | `OnMembersLeft` | `OnMembersLeft` | `OnKicked` | / |
| William 加入 | `OnMembersJoined` | `OnMembersJoined` | / | `OnMembersJoined` |
| Jerry 主动退出 | `OnMembersLeft` | `OnMembersLeft` | / | `OnMembersLeft` |

| 操作 | Tom | Jerry | Mary | William |
| --- | --- | --- | --- | --- |
| Tom 添加 Mary | `onMemberJoined` | `onMemberJoined` | `onInvited` | / |
| Tom 剔除 Mary | `onMemberLeft` | `onMemberLeft` | `onKicked` | / |
| William 加入 | `onMemberJoined` | `onMemberJoined` | / | `onMemberJoined` |
| Jerry 主动退出 | `onMemberLeft` | `onMemberLeft` | / | `onMemberLeft` |

| 操作 | Tom | Jerry | Mary | William |
| --- | --- | --- | --- | --- |
| Tom 添加 Mary | `membersAdded` | `membersAdded` | `invitedByClientId` | / |
| Tom 剔除 Mary | `membersRemoved` | `membersRemoved` | `kickedByClientId` | / |
| William 加入 | `membersAdded` | `membersAdded` | / | `membersAdded` |
| Jerry 主动退出 | `membersRemoved` | `kickedByClientId` | / | `membersRemoved` |

## 文本之外的聊天消息

上面的示例都是发送文本消息，但是实际上可能图片、视频、位置等消息也是非常常见的消息格式，接下来我们就看看如何发送这些富媒体类型的消息。

即时通讯服务默认支持文本、文件、图像、音频、视频、位置、二进制等不同格式的消息，除了二进制消息之外，普通消息的收发接口都是字符串，但是文本消息和文件、图像、音视频消息有一点区别：

* 文本消息发送的就是本身的内容
* 而其他的多媒体消息，例如一张图片，实际上即时通讯 SDK 会首先调用存储服务的 `AVFile` 接口，将图像的二进制文件上传到存储服务云端，再把图像下载的 URL 放入即时通讯消息结构体中，所以 **图像消息不过是包含了图像下载链接的固定格式文本消息** 。

图像等二进制数据不随即时通讯消息直接下发的主要原因在于，文件存储服务默认都是开通了 CDN 加速选项的，通过文件下载对于终端用户来说可以有更快的展现速度，同时对于开发者来说也能获得更低的存储成本。

### 默认消息类型

即时通讯服务内置了多种结构化消息用来满足常见的需求：

* `TextMessage` 文本消息
* `ImageMessage` 图像消息
* `AudioMessage` 音频消息
* `VideoMessage` 视频消息
* `FileMessage` 普通文件消息（.txt/.doc/.md 等各种）
* `LocationMessage` 地理位置消息

所有消息均派生自 `LCIMMessage`，每种消息实例都具备如下属性：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `content` | `String` | 消息内容。 |
| `clientId` | `String` | 消息发送者的 `clientId`。 |
| `conversationId` | `String` | 消息所属对话 ID。 |
| `messageId` | `String` | 消息发送成功之后，由云端给每条消息赋予的唯一 ID。 |
| `timestamp` | `long` | 消息发送的时间。消息发送成功之后，由云端赋予的全局的时间戳。 |
| `receiptTimestamp` | `long` | 消息被对方接收到的时间。消息被接收之后，由云端赋予的全局的时间戳。 |
| `status` | `AVIMMessageStatus` 枚举 | 消息状态，有五种取值： |

`AVIMMessageStatusNone`（未知）
`AVIMMessageStatusSending`（发送中）
`AVIMMessageStatusSent`（发送成功）
`AVIMMessageStatusReceipt`（被接收）
`AVIMMessageStatusFailed`（失败）
| `ioType` | `AVIMMessageIOType` 枚举 | 消息传输方向，有两种取值： |

`AVIMMessageIOTypeIn`（发给当前用户）
`AVIMMessageIOTypeOut`（由当前用户发出）

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `content` | `String` | 消息内容。 |
| `clientId` | `String` | 消息发送者的 `clientId`。 |
| `conversationId` | `String` | 消息所属对话 ID。 |
| `messageId` | `String` | 消息发送成功之后，由云端给每条消息赋予的唯一 ID。 |
| `timestamp` | `long` | 消息发送的时间。消息发送成功之后，由云端赋予的全局的时间戳。 |
| `receiptTimestamp` | `long` | 消息被对方接收到的时间。消息被接收之后，由云端赋予的全局的时间戳。 |
| `status` | `MessageStatus` 枚举 | 消息状态，有五种取值： |

`StatusNone`（未知）
`StatusSending`（发送中）
`StatusSent`（发送成功）
`StatusReceipt`（被接收）
`StatusFailed`（失败）
| `ioType` | `MessageIOType` 枚举 | 消息传输方向，有两种取值： |

`TypeIn`（发给当前用户）
`TypeOut`（由当前用户发出）

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `content` | `NSString` | 消息内容。 |
| `clientId` | `NSString` | 消息发送者的 `clientId`。 |
| `conversationId` | `NSString` | 消息所属对话 ID。 |
| `messageId` | `NSString` | 消息发送成功之后，由云端给每条消息赋予的唯一 ID。 |
| `sendTimestamp` | `int64_t` | 消息发送的时间。消息发送成功之后，由云端赋予的全局的时间戳。 |
| `deliveredTimestamp` | `int64_t` | 消息被对方接收到的时间。消息被接收之后，由云端赋予的全局的时间戳。 |
| `status` | `AVIMMessageStatus` 枚举 | 消息状态，有五种取值： |

`LCIMMessageStatusNone`（未知）
`LCIMMessageStatusSending`（发送中）
`LCIMMessageStatusSent`（发送成功）
`LCIMMessageStatusDelivered`（被接收）
`LCIMMessageStatusFailed`（失败）
| `ioType` | `LCIMMessageIOType` 枚举 | 消息传输方向，有两种取值： |

`LCIMMessageIOTypeIn`（发给当前用户）
`LCIMMessageIOTypeOut`（由当前用户发出）

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `from` | `String` | 消息发送者的 `clientId`。 |
| `cid` | `String` | 消息所属对话 ID。 |
| `id` | `String` | 消息发送成功之后，由云端给每条消息赋予的唯一 ID。 |
| `timestamp` | `Date` | 消息发送的时间。消息发送成功之后，由云端赋予的全局的时间戳。 |
| `deliveredAt` | `Date` | 消息送达时间。 |
| `status` | `Symbol` | 消息状态，其值为枚举 [`MessageStatus`](https://leancloud.github.io/js-realtime-sdk/docs/module-leancloud-realtime.html#.MessageStatus) 的成员之一： |

`MessageStatus.NONE`（未知）
`MessageStatus.SENDING`（发送中）
`MessageStatus.SENT`（发送成功）
`MessageStatus.DELIVERED`（已送达）
`MessageStatus.FAILED`（失败）

| 属性 | 类型 | 描述 |
| --- | --- | --- |
| `content` | `IMMessage.Content` | 消息内容，支持 `String` 和 `Data` 两种格式。 |
| `fromClientID` | `String` | 消息发送者的 `clientId`。 |
| `currentClientID` | `String` | 消息接收者的 `clientId`。 |
| `conversationID` | `String` | 消息所属对话 ID。 |
| `ID` | `String` | 消息发送成功之后，由云端给每条消息赋予的唯一 ID。 |
| `sentTimestamp` | `int64_t` | 消息发送的时间。消息发送成功之后，云端赋予的全局的时间戳。 |
| `deliveredTimestamp` | `int64_t` | 消息被对方接收到的时间戳。 |
| `readTimestamp` | `int64_t` | 消息被对方阅读的时间戳。 |
| `patchedTimestamp` | `int64_t` | 消息被修改的时间戳。 |
| `isAllMembersMentioned` | `Bool` | @ 所有会话成员。 |
| `mentionedMembers` | `[String]` | @ 会话成员。 |
| `isCurrentClientMentioned` | `Bool` | 当前 `Client` 是否被 @。 |
| `status` | `IMMessage.Status` | 消息状态，有 6 种取值： |

`none`（无状态）
`sending`（发送中）
`sent`（发送成功）
`delivered`（已被接收）
`read`（已被读）
`failed`（发送失败）
| `ioType` | `IMMessage.IOType` | 消息传输方向，有两种取值： |

`in`（当前用户接收到的）
`out`（由当前用户发出的）

我们为每一种富媒体消息定义了一个消息类型，即时通讯 SDK 自身使用的类型是负数（如下面列表所示），所有正数留给开发者自定义扩展类型使用，`0` 作为「没有类型」被保留起来。

| 消息 | 类型 |
| --- | --- |
| 文本消息 | `-1` |
| 图像消息 | `-2` |
| 音频消息 | `-3` |
| 视频消息 | `-4` |
| 位置消息 | `-5` |
| 文件消息 | `-6` |

### 图像消息

#### 发送图像文件

即时通讯 SDK 支持直接通过二进制数据，或者本地图像文件的路径，来构造一个图像消息并发送到云端。其流程如下：

sequenceDiagram Tom-->>Local: 1. 获取图像实体内容 Tom-->>Storage: 2. SDK 后台上传文件（LCFile）到云端 Storage-->>Tom: 3. 返回图像的云端地址 Tom-->>Cloud: 4. SDK 将图像消息发送给云端 Cloud->>Jerry: 5. 收到图像消息，在对话框里面做 UI 展现

图解：

  1. Local 可能是来自于 `localStorage`/`camera`，表示图像的来源可以是本地存储例如 iPhone 手机的媒体库或者直接调用相机 API 实时地拍照获取的照片。
  2. `LCFile` 是云服务提供的文件存储对象。

对应的代码并没有时序图那样复杂，因为调用 `send` 接口的时候，SDK 会自动上传图像，不需要开发者再去关心这一步：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var image =newLCFile("screenshot.png",newUri("http://example.com/screenshot.png"));
    var imageMessage =newLCIMImageMessage(image);
    imageMessage.Text ="发自我的 Windows";
    await conversation.Send(imageMessage);

    LCFile file =LCFile.withAbsoluteLocalPath("San_Francisco.png",Environment.getExternalStorageDirectory()+"/San_Francisco.png");
    // 创建一条图像消息
    LCIMImageMessage m =newLCIMImageMessage(file);
    m.setText("发自我的小米手机");
    conv.sendMessage(m,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    // 发送成功
    }
    }
    });

    NSArray *paths =NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES);
    NSString *documentsDirectory =[paths objectAtIndex:0];
    NSString *imagePath =[documentsDirectory stringByAppendingPathComponent:@"Tarara.png"];
    NSError *error;
    LCFile *file =[LCFile fileWithLocalPath:imagePath error:&error];
    LCIMImageMessage *message =[LCIMImageMessage messageWithText:@"萌妹子一枚" file:file attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    // 图像消息等富媒体消息依赖存储 SDK 和富媒体消息插件，
    // 具体的引用和初始化步骤请参考 SDK 配置指南

    var fileUploadControl =$("#photoFileUpload")[0];
    var file =newAV.File("avatar.jpg", fileUploadControl.files[0]);
    file
    .save()
    .then(function(){
    var message =newImageMessage(file);
        message.setText("发自我的 Ins");
        message.setAttributes({location:"旧金山"});
    return conversation.send(message);
    })
    .then(function(){
    console.log("发送成功");
    })
    .catch(console.error.bind(console));

    do{
    iflet imageFilePath =Bundle.main.url(forResource:"image", withExtension:"jpg")?.path {
    let imageMessage =IMImageMessage(filePath: imageFilePath, format:"jpg")
    try conversation.send(message: imageMessage, completion:{(result)in
    switch result {
    case.success:
    break
                case.failure(error:let error):
    print(error)
    }
    })
    }
    }catch{
    print(error)
    }

    import'package:flutter/services.dart'show rootBundle;

    // 假设项目根目录有 assets 文件夹存放图片，并且在 pubspec.yaml 中已经将 assets 文件夹添加到工程中。
    ByteData imageData =await rootBundle.load('assets/test.png');
    // image message
    ImageMessage imageMessage =ImageMessage.from(
      binaryData: imageData.buffer.asUint8List(),
      format:'png',
      name:'image.png',
    );
    try{
      conversation.send(message: imageMessage);
    }catch(e){
    print(e);
    }

#### 发送图像链接

除了上述这种从本地直接发送图片文件的消息之外，在很多时候，用户可能从网络上或者别的应用中拷贝了一个图像的网络连接地址，当做一条图像消息发送到对话中，这种需求可以用如下代码来实现：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var image =newLCFile("girl.gif",newUri("http://example.com/girl.gif"));
    var imageMessage =newLCIMImageMessage(image);
    imageMessage.Text ="发自我的 Windows";
    await conversation.Send(imageMessage);

    LCFile file =newLCFile("萌妹子","http://ww3.sinaimg.cn/bmiddle/596b0666gw1ed70eavm5tg20bq06m7wi.gif",null);
    LCIMImageMessage m =newLCIMImageMessage(file);
    m.setText("萌妹子一枚");
    // 创建一条图像消息
    conv.sendMessage(m,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    // 发送成功
    }
    }
    });

    // Tom 发了一张图片给 Jerry
    LCFile *file =[LCFile fileWithURL:[self@"http://ww3.sinaimg.cn/bmiddle/596b0666gw1ed70eavm5tg20bq06m7wi.gif"]];
    LCIMImageMessage *message =[LCIMImageMessage messageWithText:@"萌妹子一枚" file:file attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    varAV=require("leancloud-storage");
    var{ImageMessage}=initPlugin(AV,IM);
    // 从网络链接直接构建一个图像消息
    var file =newAV.File.withURL(
    "萌妹子",
    "http://pic2.zhimg.com/6c10e6053c739ed0ce676a0aff15cf1c.gif"
    );
    file
    .save()
    .then(function(){
    var message =newImageMessage(file);
        message.setText("萌妹子一枚");
    return conversation.send(message);
    })
    .then(function(){
    console.log("发送成功");
    })
    .catch(console.error.bind(console));

    do{
    iflet url =URL(string:"http://ww3.sinaimg.cn/bmiddle/596b0666gw1ed70eavm5tg20bq06m7wi.gif"){
    let imageMessage =IMImageMessage(url: url, format:"gif")
    try conversation.send(message: imageMessage, completion:{(result)in
    switch result {
    case.success:
    break
                case.failure(error:let error):
    print(error)
    }
    })
    }
    }catch{
    print(error)
    }

    ImageMessage imageMessage =ImageMessage.from(
      url:'http://ww3.sinaimg.cn/bmiddle/596b0666gw1ed70eavm5tg20bq06m7wi.gif',
      format:'png',
      name:'image.png',
    );
    try{
      conversation.send(message: imageMessage);
    }catch(e){
    print(e);
    }

#### 接收图像消息

图像消息的接收机制和之前是一样的，只需要修改一下接收消息的事件回调逻辑，根据消息类型来做不同的 UI 展现即可，例如：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    client.OnMessage =(conv, msg)=>{
    if(e.Message isLCIMImageMessage imageMessage){
    WriteLine(imageMessage.Url);
    }
    }

    LCIMMessageManager.registerMessageHandler(LCIMImageMessage.class,
    newLCIMTypedMessageHandler<LCIMImageMessage>(){
    @Override
    publicvoidonMessage(LCIMImageMessage msg,LCIMConversation conv,LCIMClient client){
    // 只处理 Jerry 这个客户端的消息
    // 并且来自 conversationId 为 55117292e4b065f7ee9edd29 的 conversation 的消息
    if("Jerry".equals(client.getClientId())&&"55117292e4b065f7ee9edd29".equals(conv.getConversationId())){
    String fromClientId = msg.getFrom();
    String messageId = msg.getMessageId();
    String url = msg.getFileUrl();
    Map<String,Object> metaData = msg.getFileMetaData();
    if(metaData.containsKey("size")){
    int size =(Integer) metaData.get("size");
    }
    if(metaData.containsKey("width")){
    int width =(Integer) metaData.get("width");
    }
    if(metaData.containsKey("height")){
    int height =(Integer) metaData.get("height");
    }
    if(metaData.containsKey("format")){
    String format =(String) metaData.get("format");
    }
    }
    }
    });

    -(void)conversation:(LCIMConversation *)conversation didReceiveTypedMessage:(LCIMTypedMessage *)message {
        LCIMImageMessage *imageMessage =(LCIMImageMessage *)message;

    // 消息的 ID
        NSString *messageId = imageMessage.messageId;
    // 图像文件的 URL
        NSString *imageUrl = imageMessage.file.url;
    // 发该消息的 clientId
        NSString *fromClientId = message.clientId;
    }

    var{Event,TextMessage}=require('leancloud-realtime');
    var{ImageMessage}=initPlugin(AV,IM);

    client.on(Event.MESSAGE,functionmessageEventHandler(message, conversation){
    var file;
    switch(message.type){
    caseImageMessage.TYPE:
            file = message.getFile();
    console.log('收到图像消息，URL：'+ file.url());
    break;
    }
    }

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    case.message(event:let messageEvent):
    switch messageEvent {
    case.received(message:let message):
    switch message {
    caselet imageMessage asIMImageMessage:
    print(imageMessage)
    default:
    break
    }
    default:
    break
    }
    default:
    break
    }
    }

    lient.onMessage =({
    Client client,
    Conversation conversation,
    Message message,
    }){
    if(message isImageMessage){
    print('收到图像消息，URL：${message.url}');
    }
    };

### 发送音频消息／视频／文件

#### 发送流程

对于图像、音频、视频和文件这四种类型的消息，SDK 均采取如下的发送流程：

如果文件是从 **客户端 API 读取的数据流（Stream）** ，步骤为：

  1. 从本地构造 `LCFile`
  2. 调用 `LCFile` 的上传方法将文件上传到云端，并获取文件元信息（`metaData`）
  3. 把 `LCFile` 的 `objectId`、URL、文件元信息都封装在消息体内
  4. 调用接口发送消息

如果文件是 **外部链接的 URL** ，则：

  1. 直接将 URL 封装在消息体内，不获取元信息（例如，音频消息的时长），不包含 `objectId`
  2. 调用接口发送消息

以发送音频消息为例，基本流程是：读取音频文件（或者录制音频）> 构建音频消息 > 消息发送。

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var audio =newLCFile("tante.mp3", Path.Combine(Application.persistentDataPath,"tante.mp3"));
    var audioMessage =newLCIMAudioMessage(audio);
    audioMessage.Text ="听听人类的神曲";
    await conversation.Send(audioMessage);

    LCFile file =LCFile.withAbsoluteLocalPath("忐忑.mp3",localFilePath);
    LCIMAudioMessage m =newLCIMAudioMessage(file);
    m.setText("听听人类的神曲");
    // 创建一条音频消息
    conv.sendMessage(m,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    // 发送成功
    }
    }
    });

    NSError *error = nil;
    LCFile *file =[LCFile fileWithLocalPath:localPath error:&error];
    if(!error){
        LCIMAudioMessage *message =[LCIMAudioMessage messageWithText:@"听听人类的神曲" file:file attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];
    }

    varAV=require("leancloud-storage");
    var{AudioMessage}=initPlugin(AV,IM);

    var fileUploadControl =$("#musicFileUpload")[0];
    var file =newAV.File("忐忑.mp3", fileUploadControl.files[0]);
    file
    .save()
    .then(function(){
    var message =newAudioMessage(file);
        message.setText("听听人类的神曲");
    return conversation.send(message);
    })
    .then(function(){
    console.log("发送成功");
    })
    .catch(console.error.bind(console));

    do{
    iflet filePath =Bundle.main.url(forResource:"audio", withExtension:"mp3")?.path {
    let audioMessage =IMAudioMessage(filePath: filePath, format:"mp3")
            audioMessage.text ="听听人类的神曲"
    try conversation.send(message: audioMessage, completion:{(result)in
    switch result {
    case.success:
    break
                case.failure(error:let error):
    print(error)
    }
    })
    }
    }catch{
    print(error)
    }

    import'package:flutter/services.dart'show rootBundle;

    // 假设项目根目录有 assets 文件夹存放 mp3 文件，并且在 pubspec.yaml 中已经将 assets 文件夹添加到工程中。
    ByteData audioData =await rootBundle.load('assets/test.mp3');
    AudioMessage audioMessage =AudioMessage.from(
      binaryData: audioData.buffer.asUint8List(),
      format:'mp3',
    );
    audioMessage.text ='听听人类的神曲';
    try{
    await conversation.send(message: audioMessage);
    }catch(e){
    print(e);
    }

与图像消息类似，音频消息也支持从 URL 构建：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var audio =newLCFile("apple.aac",newUri("https://some.website.com/apple.aac"));
    var audioMessage =newLCIMAudioMessage(audio);
    audioMessage.Text ="来自苹果发布会现场的录音";
    await conversation.Send(audioMessage);

    LCFile file =newLCFile("apple.aac","https://some.website.com/apple.aac",null);
    LCIMAudioMessage m =newLCIMAudioMessage(file);
    m.setText("来自苹果发布会现场的录音");
    conv.sendMessage(m,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
    // 发送成功
    }
    }
    });

    LCFile *file =[LCFile fileWithRemoteURL:[NSURL URLWithString:@"https://some.website.com/apple.aac"]];
    LCIMAudioMessage *message =[LCIMAudioMessage messageWithText:@"来自苹果发布会现场的录音" file:file attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    varAV=require("leancloud-storage");
    var{AudioMessage}=initPlugin(AV,IM);

    var file =newAV.File.withURL(
    "apple.aac",
    "https://some.website.com/apple.aac"
    );
    file
    .save()
    .then(function(){
    var message =newAudioMessage(file);
        message.setText("来自苹果发布会现场的录音");
    return conversation.send(message);
    })
    .then(function(){
    console.log("发送成功");
    })
    .catch(console.error.bind(console));

    do{
    iflet url =URL(string:"https://some.website.com/apple.aac"){
    let audioMessage =IMAudioMessage(url: url, format:"aac")
            audioMessage.text ="来自苹果发布会现场的录音"
    try conversation.send(message: audioMessage, completion:{(result)in
    switch result {
    case.success:
    break
                case.failure(error:let error):
    print(error)
    }
    })
    }
    }catch{
    print(error)
    }

    AudioMessage audioMessage =AudioMessage.from(
      url:'https://some.website.com/apple.aac',
      name:'apple.aac',
    );
    try{
    await conversation.send(message: audioMessage);
    }catch(e){
    print(e);
    }

### 发送地理位置消息

地理位置消息构建方式如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var location =newLCGeoPoint(31.3753285,120.9664658);
    var locationMessage =newLCIMLocationMessage(location);
    await conversation.Send(locationMessage);

    finalLCIMLocationMessage locationMessage =newLCIMLocationMessage();
    // 开发者可以通过设备的 API 获取设备的具体地理位置，此处设置了 2 个经纬度常量作为演示
    locationMessage.setLocation(newLCGeoPoint(31.3753285,120.9664658));
    locationMessage.setText("蛋糕店的位置");
    conversation.sendMessage(locationMessage,newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(null!= e){
              e.printStackTrace();
    }else{
    // 发送成功
    }
    }
    });

    LCIMLocationMessage *message =[LCIMLocationMessage messageWithText:@"蛋糕店的位置" latitude:31.3753285 longitude:120.9664658 attributes:nil];
    [conversation sendMessage:message callback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"发送成功！");
    }
    }];

    varAV=require("leancloud-storage");
    var{LocationMessage}=initPlugin(AV,IM);

    varlocation=newAV.GeoPoint(31.3753285,120.9664658);
    var message =newLocationMessage(location);
    message.setText("蛋糕店的位置");
    conversation
    .send(message)
    .then(function(){
    console.log("发送成功");
    })
    .catch(console.error.bind(console));

    do{
    let locationMessage =IMLocationMessage(latitude:31.3753285, longitude:120.9664658)
    try conversation.send(message: locationMessage, completion:{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    LocationMessage locationMessage =LocationMessage.from(
      latitude:22,
      longitude:33,
    );
    try{
    await conversation.send(message: locationMessage);
    }catch(e){
    print(e);
    }

### 再谈接收消息

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

C# SDK 通过 `OnMessage` 事件回调来通知新消息：

    jerry.OnMessage =(conv, msg)=>{
    if(msg isLCIMImageMessage imageMessage){

    }elseif(msg isLCIMAudioMessage audioMessage){

    }elseif(msg isLCIMVideoMessage videoMessage){

    }elseif(msg isLCIMFileMessage fileMessage){

    }elseif(msg isAVIMLocationMessage locationMessage){

    }elseif(msg isInputtingMessage){
    WriteLine($"收到自定义消息 {inputtingMessage.TextContent}{inputtingMessage.Ecode}");
    }
    }

Java/Android SDK 中定义了 `LCIMMessageHandler` 接口来通知应用层新消息到达事件发生，开发者通过调用 `LCIMMessageManager.registerDefaultMessageHandler` 方法来注册自己的消息处理函数。`LCIMMessageManager` 提供了两个不同的方法来注册默认的消息处理函数，或特定类型的消息处理函数：

    /**
     * 注册默认的消息 handler
     *
     * @param handler
     */
    publicstaticvoidregisterDefaultMessageHandler(LCIMMessageHandler handler);
    /**
     * 注册特定消息格式的处理单元
     *
     * @param clazz 特定的消息类
     * @param handler
     */
    publicstaticvoidregisterMessageHandler(Class<?extendsLCIMMessage> clazz,MessageHandler<?> handler);
    /**
     * 取消特定消息格式的处理单元
     *
     * @param clazz
     * @param handler
     */
    publicstaticvoidunregisterMessageHandler(Class<?extendsLCIMMessage> clazz,MessageHandler<?> handler);

消息处理函数需要在应用初始化时完成设置，理论上我们支持为每一种消息（包括应用层自定义的消息）分别注册不同的消息处理函数，并且也支持取消注册。

多次调用 `LCIMMessageManager` 的 `registerDefaultMessageHandler`，只有最后一次调用有效；而通过 `registerMessageHandler` 注册的 `LCIMMessageHandler`，则是可以同存的。

当客户端收到一条消息的时候，SDK 内部的处理流程为：

* 首先解析消息的类型，然后找到开发者为这一类型所注册的处理响应 handler chain，再逐一调用这些 handler 的 `onMessage` 函数。
* 如果没有找到专门处理这一类型消息的 handler，就会转交给 `defaultHandler` 处理。

这样一来，在开发者为 `AVIMTypedMessage`（及其子类）指定了专门的 handler，也指定了全局的 `defaultHandler` 了的时候，如果发送端发送的是通用的 `LCIMMessage` 消息，那么接收端就是 `LCIMMessageManager.registerDefaultMessageHandler()` 中指定的 handler 被调用；如果发送的是 `LCIMTypedMessage`（及其子类）的消息，那么接收端就是 `LCIMMessageManager.registerMessageHandler()` 中指定的 handler 被调用。

    // 1. 注册默认 handler，只有其他 handle 都没有被调用到时才会调用
    LCIMMessageManager.registerDefaultMessageHandler(newLCIMMessageHandler(){
    publicvoidonMessage(LCIMMessage message,LCIMConversation conversation,LCIMClient client){
    // 接收消息
    }

    publicvoidonMessageReceipt(LCIMMessage message,LCIMConversation conversation,LCIMClient client){
    // 未来可能添加新的自定义消息类型，新版 SDK 也可能添加新的消息类型。
    // 因此别忘了在这里处理未知类型，例如提示用户升级客户端至最新版本。
    }
    });
    // 2. 为每一种消息类型注册 handler
    LCIMMessageManager.registerMessageHandler(LCIMTypedMessage.class,newLCIMTypedMessageHandler<LCIMTypedMessage>(){
    publicvoidonMessage(LCIMTypedMessage message,LCIMConversation conversation,LCIMClient client){
    switch(message.getMessageType()){
    caseLCIMMessageType.TEXT_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMTextMessage textMessage =(LCIMTextMessage)message;
    break;
    caseLCIMMessageType.IMAGE_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMImageMessage imageMessage =(LCIMImageMessage)message;
    break;
    caseLCIMMessageType.AUDIO_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMAudioMessage audioMessage =(LCIMAudioMessage)message;
    break;
    caseLCIMMessageType.VIDEO_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMVideoMessage videoMessage =(LCIMVideoMessage)message;
    break;
    caseLCIMMessageType.LOCATION_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMLocationMessage locationMessage =(LCIMLocationMessage)message;
    break;
    caseLCIMMessageType.FILE_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMFileMessage fileMessage =(LCIMFileMessage)message;
    break;
    caseLCIMMessageType.RECALLED_MESSAGE_TYPE:
    // 执行其他逻辑
    LCIMRecalledMessage recalledMessage =(LCIMRecalledMessage)message;
    break;
    case123:
    // 这是一个自定义消息类型
    // 执行其他逻辑
    CustomMessage customMessage =(CustomMessage)message;
    break;
    }
    }

    publicvoidonMessageReceipt(LCIMTypedMessage message,LCIMConversation conversation,LCIMClient client){
    // 执行收到消息后的逻辑
    }
    });

Objective-C SDK 是通过实现 `LCIMClientDelegate` 代理来响应新消息到达通知的，并且，分别使用了两个方法来分别处理普通的 `LCIMMessage` 消息和内建的多媒体消息 `LCIMTypedMessage`（包括应用层由此派生的自定义消息：

    /*!
     接收到新的普通消息。
     @param conversation － 所属对话
     @param message - 具体的消息
     */
    -(void)conversation:(LCIMConversation *)conversation didReceiveCommonMessage:(LCIMMessage *)message;

    /*!
     接收到新的富媒体消息。
     @param conversation － 所属对话
     @param message - 具体的消息
     */
    -(void)conversation:(LCIMConversation *)conversation didReceiveTypedMessage:(LCIMTypedMessage *)message;

    // 处理默认类型消息
    -(void)conversation:(LCIMConversation *)conversation didReceiveTypedMessage:(LCIMTypedMessage *)message {
    if(message.mediaType == LCIMMessageMediaTypeImage){
            LCIMImageMessage *imageMessage =(LCIMImageMessage *)message;// 处理图像消息
    }elseif(message.mediaType == LCIMMessageMediaTypeAudio){
    // 处理音频消息
    }elseif(message.mediaType == LCIMMessageMediaTypeVideo){
    // 处理视频消息
    }elseif(message.mediaType == LCIMMessageMediaTypeLocation){
    // 处理位置消息
    }elseif(message.mediaType == LCIMMessageMediaTypeFile){
    // 处理文件消息
    }elseif(message.mediaType == LCIMMessageMediaTypeText){
    // 处理文本消息
    }elseif(message.mediaType ==123){
    // 处理自定义的消息类型
    }
    }

    // 处理未知消息类型
    -(void)conversation:(LCIMConversation *)conversation didReceiveCommonMessage:(LCIMMessage *)message {
    // 未来可能添加新的自定义消息类型，新版 SDK 也可能添加新的消息类型。
    // 因此别忘了在这里处理未知类型，例如提示用户升级客户端至最新版本。
    }

不管消息类型如何，JavaScript SDK 都是是通过 `IMClient` 上的 `Event.MESSAGE` 事件回调来通知新消息的，应用层只需要在一个地方，统一对不同类型的消息使用不同方式来处理即可。

    // 在初始化 Realtime 时，需加载 TypedMessagesPlugin
    var{Event,TextMessage}=require("leancloud-realtime");
    var{FileMessage,ImageMessage,AudioMessage,VideoMessage,LocationMessage}=
    initPlugin(AV,IM);
    // 注册 MESSAGE 事件的 handler
    client.on(Event.MESSAGE,functionmessageEventHandler(message, conversation){
    // 请按自己需求改写
    var file;
    switch(message.type){
    caseTextMessage.TYPE:
    console.log(
    "收到文本消息，内容："+ message.getText()+"，ID："+ message.id
    );
    break;
    caseFileMessage.TYPE:
          file = message.getFile();// file 是 AV.File 实例
    console.log(
    "收到文件消息，URL："+ file.url()+"，大小："+ file.metaData("size")
    );
    break;
    caseImageMessage.TYPE:
          file = message.getFile();
    console.log(
    "收到图像消息，URL："+ file.url()+"，宽度："+ file.metaData("width")
    );
    break;
    caseAudioMessage.TYPE:
          file = message.getFile();
    console.log(
    "收到音频消息，URL："+
              file.url()+
    "，长度："+
              file.metaData("duration")
    );
    break;
    caseVideoMessage.TYPE:
          file = message.getFile();
    console.log(
    "收到视频消息，URL："+
              file.url()+
    "，长度："+
              file.metaData("duration")
    );
    break;
    caseLocationMessage.TYPE:
    varlocation= message.getLocation();
    console.log(
    "收到位置消息，纬度："+
    location.latitude+
    "，经度："+
    location.longitude
    );
    break;
    case1:
    console.log("OperationMessage 是自定义消息类型");
    default:
    // 未来可能添加新的自定义消息类型，新版 SDK 也可能添加新的消息类型。
    // 因此别忘了在默认分支中处理未知类型，例如提示用户升级客户端至最新版本。
    console.warn("收到未知类型消息");
    }
    });

    // 同时，对应的 conversation 上也会派发 `MESSAGE` 事件：
    conversation.on(Event.MESSAGE,functionmessageEventHandler(message){
    // 这里补充业务逻辑
    });

Swift SDK 是通过实现 `IMClientDelegate` 代理来响应新消息到达通知的：

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    case.message(event:let messageEvent):
    switch messageEvent {
    case.received(message:let message):
    print(message)
    default:
    break
    }
    default:
    break
    }
    }

    // 处理默认类型消息
    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    case.message(event:let messageEvent):
    switch messageEvent {
    case.received(message:let message):
    iflet categorizedMessage = message as?IMCategorizedMessage{
    switch categorizedMessage {
    caselet textMessage asIMTextMessage:
    print(textMessage)
    caselet imageMessage asIMImageMessage:
    print(imageMessage)
    caselet audioMessage asIMAudioMessage:
    print(audioMessage)
    caselet videoMessage asIMVideoMessage:
    print(videoMessage)
    caselet fileMessage asIMFileMessage:
    print(fileMessage)
    caselet locationMessage asIMLocationMessage:
    print(locationMessage)
    caselet recalledMessage asIMRecalledMessage:
    print(recalledMessage)
    caselet customMessage asCustomMessage:
    print("customMessage 是自定义消息类型")
    default:
    break
    }else{
    // 未来可能添加新的自定义消息类型，新版 SDK 也可能添加新的消息类型。
    // 因此别忘了在默认分支中处理未知类型，例如提示用户升级客户端至最新版本。
    print("收到未知类型消息")
    }
    default:
    break
    }
    default:
    break
    }
    }

    jerry.onMessage =({
    Client client,
    Conversation conversation,
    Message message,
    }){
    if(message.binaryContent !=null){
    print('收到二进制消息：${message.binaryContent.toString()}');
    }elseif(message isTextMessage){
    print('收到文本类型消息：${message.text}');
    }elseif(message isLocationMessage){
    print('收到地理位置消息，坐标：${message.latitude},${message.longitude}');
    }elseif(message isFileMessage){
    if(message isImageMessage){
    print('收到图像消息，图像 URL：${message.url}');
    }elseif(message isAudioMessage){
    print('收到音频消息，消息时长：${message.duration}');
    }elseif(message isVideoMessage){
    print('收到视频消息，消息时长：${message.duration}');
    }else{
    print('收到 .txt/.doc/.md 等各种类型的普通文件消息，URL：${message.url}');
    }
    }elseif(message isCustomMessage){
    // CustomMessage 是自定义的消息类型
    print('收到自定义类型消息');
    }else{
    // 这里可以继续添加自定义类型的判断条件
    print('收到未知消息类型');
    if(message.stringContent !=null){
    print('收到普通消息：${message.stringContent}');
    }
    }
    };

上面的代码示例中涉及到接收自定义消息。 我们将在[即时通讯开发指南第二篇](intermediate/)的《自定义消息类型》一节介绍。

## 扩展对话：支持自定义属性

「对话（`Conversation`）」是即时通讯的核心逻辑对象，它有一些内置的常用的属性，与控制台中 `_Conversation` 表是一一对应的。默认提供的 **内置** 属性的对应关系如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

| `AVIMConversation` 属性名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `CurrentClient` | N/A | 对话所属的 `AVIMClient` 对象 |
| `ConversationId` | `objectId` | 全局唯一的 ID |
| `Name` | `name` | 成员共享的统一的名字 |
| `MemberIds` | `m` | 成员列表 |
| `MuteMemberIds` | `mu` | 静音该对话的成员 |
| `Creator` | `c` | 对话创建者 |
| `IsTransient` | `tr` | 是否为聊天室 |
| `IsSystem` | `sys` | 是否为系统对话 |
| `IsUnique` | `unique` | 是否为相同成员的唯一对话 |
| `IsTemporary` | N/A | 是否为临时对话（临时对话数据不保存到 `_Conversation` 表中 ） |
| `CreatedAt` | `createdAt` | 创建时间 |
| `UpdatedAt` | `updatedAt` | 最后更新时间 |
| `LastMessageAt` | `lm` | 该对话最后一条消息，也可以理解为最后一次活跃时间 |

| `LCIMConversation` get 方法名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `getAttributes` | `attr` | 自定义属性 |
| `getConversationId` | `objectId` | 全局唯一的 ID |
| `getCreatedAt` | `createdAt` | 创建时间 |
| `getCreator` | `c` | 对话创建者 |
| `getLastDeliveredAt` | N/A | （仅限单聊）最后一条已送达对方的消息时间 |
| `getLastMessage` | N/A | 最后一条消息，可能会空 |
| `getLastMessageAt` | `lm` | 该对话最后一条消息，也可以理解为最后一次活跃时间 |
| `getLastReadAt` | N/A | （仅限单聊）最后一条对方已读的消息时间 |
| `getMembers` | `m` | 成员列表 |
| `getName` | `name` | 成员共享的统一的名字 |
| `getTemporaryExpiredat` | N/A | 临时对话存活时间 |
| `getUniqueId` | `uniqueId` | `Unique Conversation` 全局唯一的 `ID` |
| `getUnreadMessagesCount` | N/A | 未读消息数 |
| `getUpdatedAt` | `updatedAt` | 最后更新时间 |
| `isSystem` | `sys` | 是否为系统对话 |
| `isTemporary` | N/A | 是否为临时对话（临时对话数据不保存到 `_Conversation` 表中 ） |
| `isTransient` | `tr` | 是否为聊天室 |
| `isUnique` | `unique` | 是否是 `Unique Conversation` |
| `unreadMessagesMentioned` | N/A | 未读消息是否 @ 了当前的 `Client` |

| `LCIMConversation` 属性名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `clientID` | N/A | 会话所属的 `Client` 的 `ID` |
| `conversationId` | `objectId` | 全局唯一的 ID |
| `creator` | `c` | 对话创建者 |
| `createdAt` | `createdAt` | 创建时间 |
| `updatedAt` | `updatedAt` | 最后更新时间 |
| `lastMessage` | N/A | 最后一条消息，可能会空 |
| `lastMessageAt` | `lm` | 最后一条消息发送时间，也可以理解为最后一次活跃时间 |
| `lastReadAt` | N/A | （仅限单聊）最后一条对方已读的消息时间 |
| `lastDeliveredAt` | N/A | （仅限单聊）最后一条已送达对方的消息时间 |
| `unreadMessagesCount` | N/A | 未读消息数 |
| `unreadMessageContainMention` | N/A | 未读消息是否 @ 了当前的 `Client` |
| `name` | `name` | 成员共享的统一的名字 |
| `members` | `m` | 成员列表 |
| `attributes` | `attr` | 自定义属性 |
| `uniqueId` | `uniqueId` | `Unique Conversation` 全局唯一的 `ID` |
| `unique` | `unique` | 是否是 `Unique Conversation` |
| `transient` | `tr` | 是否为暂态会话 |
| `system` | `sys` | 是否为系统对话 |
| `temporary` | N/A | 是否为临时对话（临时对话数据不保存到 `_Conversation` 表中 ） |
| `temporaryTTL` | N/A | 临时对话存活时间 |
| `muted` | N/A | 当前用户是否静音该对话 |
| `imClient` | N/A | 对话所属的 `LCIMClient` 对象 |

| `Conversation` 属性名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `createdAt` | `createdAt` | 创建时间 |
| `creator` | `c` | 对话创建者 |
| `id` | `objectId` | 全局唯一的 ID |
| `lastDeliveredAt` | N/A | （仅限单聊）最后一条已送达对方的消息时间 |
| `lastMessage` | N/A | 最后一条消息，可能会空 |
| `lastMessageAt` | `lm` | 最后一条消息发送时间，也可以理解为最后一次活跃时间 |
| `lastReadAt` | N/A | （仅限单聊）最后一条对方已读的消息时间 |
| `members` | `m` | 成员列表 |
| `muted` | N/A | 当前用户是否静音该对话 |
| `mutedMembers` | `mu` | 静音该对话的成员 |
| `name` | `name` | 成员共享的统一的名字 |
| `system` | `sys` | 是否为服务号（系统对话） |
| `transient` | `tr` | 是否为暂态会话 |
| `unreadMessagesCount` | N/A | 未读消息数 |
| `updatedAt` | `updatedAt` | 最后更新时间 |

| `IMConversation` 属性名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `client` | N/A | 会话所属的 `Client` |
| `ID` | `objectId` | 会话的全局唯一 `ID` |
| `clientID` | N/A | 会话所属的 `Client` 的 `ID` |
| `isUnique` | `unique` | 是否是 `Unique Conversation` |
| `uniqueID` | `uniqueId` | `Unique Conversation` 全局唯一的 `ID` |
| `name` | `name` | 会话的名称 |
| `creator` | `c` | 会话的创建者 |
| `createdAt` | `createdAt` | 会话的创建时间 |
| `updatedAt` | `updatedAt` | 会话的最后更新时间 |
| `attributes` | `attr` | 会话的自定义属性 |
| `members` | `m` | 会话的成员列表 |
| `isMuted` | N/A | 当前用户是否静音该对话 |
| `isOutdated` | N/A | 会话的属性是否过期，可以根据该属性来决定是否更新会话的数据 |
| `lastMessage` | N/A | 最新一条消息，可能会空 |
| `unreadMessageCount` | N/A | 未读消息数 |
| `isUnreadMessageContainMention` | N/A | 未读消息是否 @ 了当前的 `Client` |
| `memberInfoTable` | N/A | 成员信息表 |

| `Conversation` 属性名 | `_Conversation` 字段 | 含义 |
| --- | --- | --- |
| `attributes` | `attr` | 自定义属性 |
| `client` | N/A | 对话所属的 `Client` 对象 |
| `createdAt` | `createdAt` | 创建时间 |
| `creator` | `c` | 对话创建者 |
| `id` | `objectId` | 全局唯一的 ID |
| `isMuted` | N/A | 当前用户是否静音该对话 |
| `isUnique` | `unique` | 是否是 `Unique Conversation` |
| `lastDeliveredAt` | N/A | （仅限单聊）最后一条已送达对方的消息时间 |
| `lastMessage` | N/A | 最后一条消息，可能会空 |
| `lastReadAt` | N/A | （仅限单聊）最后一条对方已读的消息时间 |
| `members` | `m` | 成员列表 |
| `name` | `name` | 成员共享的统一的名字 |
| `uniqueID` | `uniqueId` | `Unique Conversation` 的唯一 ID |
| `unreadMessagesCount` | N/A | 未读消息数 |
| `unreadMessagesMentioned` | N/A | 未读消息是否 @ 了当前的 `Client` |
| `updatedAt` | `updatedAt` | 最后更新时间 |

不过，我们不建议直接对 `_Conversation` 进行写操作，因为：

* 客户端 SDK 查询会话数据是走 websocket 长连接，会首先从即时通讯服务器的内存缓存中查。直接操作 `_Conversation` 表，不会更新即时通讯服务器的缓存，这就带来了缓存不一致问题。
* 直接操作 `_Conversation` 表的情况下，即时通讯服务器不会下发相应的事件通知客户端，客户端自然也就无从响应。
* 如果定义了即时通讯服务的 hook 函数，直接操作 `_Conversation` 表不会触发这些 hook。

如有管理需求，我们推荐调用专门的即时通讯 REST API 接口。

另外，我们可以通过「自定义属性」来在「对话」中保存更多业务层数据。

### 创建自定义属性

在最开始介绍 [创建单聊对话](#%E5%88%9B%E5%BB%BA%E5%AF%B9%E8%AF%9D-conversation) 的时候，我们提到过 `IMClient#createConversation` 接口支持附加自定义属性，现在我们就来演示一下如何使用自定义属性。

假如在创建对话的时候，我们需要添加两个额外的属性值对 `{ "type": "private", "pinned": true }`，那么在调用 `IMClient#createConversation` 方法时可以把附加属性传进去：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var properties =newDictionary<string,object>{
    {"type","private"},
    {"pinned",true}
    };
    var conversation =await tom.CreateConversation("Jerry",name:"Tom & Jerry",unique:true,properties: properties);

    HashMap<String,Object> attr =newHashMap<String,Object>();
    attr.put("type","private");
    attr.put("pinned",true);
    client.createConversation(Arrays.asList("Jerry"),"猫和老鼠", attr,false,true,
    newLCIMConversationCreatedCallback(){
    @Override
    publicvoiddone(LCIMConversation conv,LCIMException e){
    if(e==null){
    // 创建成功
    }
    }
    });

    // Tom 创建名称为「猫和老鼠」的会话，并附加会话属性
    LCIMConversationCreationOption *option =[LCIMConversationCreationOption new];
    option.name =@"猫和老鼠";
    option.attributes =@{
    @"type":@"private",
    @"pinned":@(YES)
    };
    [self createConversationWithClientIds:@[@"Jerry"] option:option callback:^(LCIMConversation * _Nullable conversation, NSError * _Nullable error){
    if(succeeded){
    NSLog(@"创建成功！");
    }
    }];

    tom
    .createConversation({
    members:["Jerry"],
    name:"猫和老鼠",
    unique:true,
    type:"private",
    pinned:true,
    })
    .then(function(conversation){
    console.log("创建成功。ID："+ conversation.id);
    })
    .catch(console.error.bind(console));

    do{
    try tom.createConversation(clientIDs:["Jerry"], name:"猫和老鼠", attributes:["type":"private","pinned":true], isUnique:true, completion:{(result)in
    switch result {
    case.success(value:let conversation):
    print(conversation)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    Conversation conversation =await jerry.createConversation(
        members:{'client1.id','client2.id'},
        attributes:{
    'members':['Jerry'],
    'name':'猫和老鼠',
    'unique':true,
    'type':'private',
    'pinned':true,
    },
    );
    }catch(e){
    print(e);
    }

**自定义属性在 SDK 级别是对所有成员可见的。** 我们也支持通过自定义属性来查询对话，请参见 [使用复杂条件来查询对话](#%E4%BD%BF%E7%94%A8%E5%A4%8D%E6%9D%82%E6%9D%A1%E4%BB%B6%E6%9D%A5%E6%9F%A5%E8%AF%A2%E5%AF%B9%E8%AF%9D)。

### 修改和使用属性

在 `Conversation` 对象中，系统默认提供的属性，例如对话的名字（`name`），如果业务层没有限制的话，所有成员都是可以修改的，示例代码如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await conversation.UpdateInfo(newDictionary<string,object>{
    {"name","聪明的喵星人"}
    });

    LCIMConversation conversation = client.getConversation("55117292e4b065f7ee9edd29");
    conversation.setName("聪明的喵星人");
    conversation.updateInfoInBackground(newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e==null){
    // 更新成功
    }
    }
    });

    conversation[@"name"]=@"聪明的喵星人";
    [conversation updateWithCallback:^(BOOL succeeded, NSError * _Nullable error){
    if(succeeded){
    NSLog(@"修改成功！");
    }
    }];

    conversation.name="聪明的喵星人";
    conversation.save();

    do{
    try conversation.update(attribution:["name":"聪明的喵星人"], completion:{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    await conversation.updateInfo(attributes:{
    'name':'聪明的喵星人',
    });
    }catch(e){
    print(e);
    }

而 `Conversation` 对象中自定义的属性，即时通讯服务也是允许对话内其他成员来读取、使用和修改的，示例代码如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // 获取自定义属性
    var type = conversation["type"];
    // 为 pinned 属性设置新的值
    await conversation.UpdateInfo(newDictionary<string,object>{
    {"pinned",false}
    });

    // 获取自定义属性
    String type = conversation.get("attr.type");
    // 为 pinned 属性设置新的值
    conversation.set("attr.pinned",false);
    // 保存
    conversation.updateInfoInBackground(newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e==null){
    // 更新成功
    }
    }
    });

    // 获取自定义属性
    NSString *type = conversation.attributes[@"type"];
    // 为 pinned 属性设置新的值
    [conversation setObject:@(NO) forKey:@"attr.pinned"];
    // 保存
    [conversation updateWithCallback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"修改成功！");
    }
    }];

    // 获取自定义属性
    var type = conversation.get("attr.type");
    // 为 pinned 属性设置新的值
    conversation.set("attr.pinned",false);
    // 保存
    conversation.save();

    do{
    let type = conversation.attributes?["type"]as?String
    try conversation.update(attribution:["attr.pinned":false]){(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    try{
    // 获取自定义属性
    String type = conversation.attributes['type'];
    // 为 pinned 属性设置新的值
    await conversation.updateInfo(attributes:{
    'pinned':false,
    });
    }catch(e){
    print(e);
    }

对自定义属性名的说明

在 `IMClient#createConversation` 接口中指定的自定义属性，会被存入 `_Conversation` 表的 `attr` 字段，所以在之后对这些属性进行读取或修改的时候，属性名需要指定完整的路径，例如上面的 `attr.type`，这一点需要特别注意。

### 对话属性同步

对话的名字以及应用层附加的其他属性，一般都是需要全员共享的，一旦有人对这些数据进行了修改，那么就需要及时通知到全部成员。在前一个例子中，有一个用户对话名称改为了「聪明的喵星人」，那其他成员怎么能知道这件事情呢？

即时通讯云端提供了实时同步的通知机制，会把单个用户对「对话」的修改同步下发到所有在线成员（对于非在线的成员，他们下次登录上线之后，自然会拉取到最新的完整的对话数据）。对话属性更新的通知事件声明如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    jerry.OnConversationInfoUpdated =(conv, attrs, initBy)=>{
    WriteLine($"对话：${conv.Id} 被更新");
    };

    // 在 LCIMConversationEventHandler 接口中有如下定义
    /**
     * 对话自身属性变更通知
     *
     * @param client
     * @param conversation
     * @param attr      被更新的属性
     * @param operator  该操作的发起者 ID
     */
    publicvoidonInfoChanged(LCIMClient client,LCIMConversation conversation,JSONObject attr,
    String operator)

    /// Notification for conversation's attribution updated.
    /// @param conversation Updated conversation.
    /// @param date Updated date.
    /// @param clientId Client ID which do this update.
    /// @param updatedData Updated data.
    /// @param updatingData Updating data.
    -(void)conversation:(LCIMConversation *)conversation didUpdateAt:(NSDate * _Nullable)date byClientId:(NSString * _Nullable)clientId updatedData:(NSDictionary * _Nullable)updatedData updatingData:(NSDictionary * _Nullable)updatingData;

    /**
     * 对话信息被更新
     * @event IMClient#CONVERSATION_INFO_UPDATED
     * @param {Object} payload
     * @param {Object} payload.attributes 被更新的属性
     * @param {String} payload.updatedBy 该操作的发起者 ID
     */
    var{Event}=require("leancloud-realtime");
    client.on(Event.CONVERSATION_INFO_UPDATED,function(payload){});

    funcclient(_ client:IMClient, conversation:IMConversation, event:IMConversationEvent){
    switch event {
    caselet.dataUpdated(updatingData: updatingData, updatedData: updatedData, byClientID: byClientID, at: atDate):
    print(updatingData)
    print(updatedData)
    print(byClientID)
    print(atDate)
    default:
    break
    }
    }

    jerry.onInfoUpdated =({
    Client client,
    Conversation conversation,
    Map updatingAttributes,
    Map updatedAttributes,
    String byClientID,
    DateTime atDate,
    }){
    print('会话：${conversation.id} 被更新');
    };

使用提示：

应用层在该事件的响应函数中，可以获知当前什么属性被修改了，也可以直接从 SDK 的 `Conversation` 实例中获取最新的合并之后的属性值，然后依据需要来更新产品 UI。

### 获取群内成员列表

群内成员列表是作为对话的属性持久化保存在云端的，所以要获取一个 `Conversation` 对象的成员列表，我们可以在调用这个对象的更新方法之后，直接获取成员属性即可。

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await conversation.Fetch();

    // fetchInfoInBackground 方法会执行一次刷新操作，以获取云端最新对话数据。
    conversation.fetchInfoInBackground(newLCIMConversationCallback(){
    @Override
    publicvoiddone(LCIMException e){
    if(e ==null){
          conversation.getMembers();
    }
    }
    });

    // fetchWithCallback 方法会执行一次刷新操作，以获取云端最新对话数据。
    [conversation fetchWithCallback:^(BOOL succeeded, NSError *error){
    if(succeeded){
    NSLog(@"", conversation.members);
    }
    }];

    // fetch 方法会执行一次刷新操作，以获取云端最新对话数据。
    conversation.fetch().then(function(conversation){
    console.log('members: ', conversation.members);
    ).catch(console.error.bind(console));

    do{
    try conversation.refresh {(result)in
    switch result {
    case.success:
    iflet members = conversation.members {
    print(members)
    }
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    // 暂不支持

使用提示：

成员列表是对 **_普通对话_** 而言的，对于像「聊天室」「系统对话」这样的特殊对话，并不存在「成员列表」属性。

## 使用复杂条件来查询对话

除了在事件通知接口中获得 `Conversation` 实例之外，开发者也可以根据不同的属性和条件来查询 `Conversation` 对象。例如有些产品允许终端用户根据名字或地理位置来匹配感兴趣聊天室，也有些业务场景允许查询成员列表中包含特定用户的所有对话，这些都可以通过对话查询的接口实现。

### 根据 ID 查询

ID 对应就是 `_Conversation` 表中的 `objectId` 的字段值，这是一种最简单也最高效的查询（因为云端会对 ID 建立索引）：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var query = tom.GetQuery();
    var conversation =await query.Get("551260efe4b01608686c3e0f");

    LCIMConversationsQuery query = tom.getConversationsQuery();
    query.whereEqualTo("objectId","551260efe4b01608686c3e0f");
    query.findInBackground(newLCIMConversationQueryCallback(){
    @Override
    publicvoiddone(List<LCIMConversation> convs,LCIMException e){
    if(e==null){
    if(convs!=null&&!convs.isEmpty()){
    // convs.get(0) 就是想要的 conversation
    }
    }
    }
    });

    LCIMConversationQuery *query =[tom conversationQuery];
    [query getConversationById:@"551260efe4b01608686c3e0f" callback:^(LCIMConversation *conversation, NSError *error){
    if(succeeded){
    NSLog(@"查询成功！");
    }
    }];

    tom
    .getConversation("551260efe4b01608686c3e0f")
    .then(function(conversation){
    console.log(conversation.id);
    })
    .catch(console.error.bind(console));

    do{
    let conversationQuery = tom.conversationQuery
    try conversationQuery.getConversation(by:"551260efe4b01608686c3e0f"){(result)in
    switch result {
    case.success(value:let conversation):
    print(conversation)
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    // 我们建议开发者首先尝试从内存中获取对话，以减少不必要的网络请求。

    String convID ='551260efe4b01608686c3e0f';
    Conversation conversation = tom.conversationMap[convID];
    if(conversation ==null){
    try{
    ConversationQuery query = tom.conversationQuery();
        query.whereEqualTo('objectId', convID);
        conversation =await query.find();
    }catch(e){
    print(e);
    }
    }

### 基础的条件查询

即时通讯 SDK 提供了丰富的条件查询方式，可以满足各种复杂的业务需求。

我们首先从最简单的 `equalTo` 开始。例如查询所有自定义属性 `type`（字符串类型）为 `private` 的对话，需要如下代码：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var query = tom.GetQuery()
    .WhereEqualTo("type","private");
    await query.Find();

    LCIMConversationsQuery query = tom.getConversationsQuery();
    query.whereEqualTo("attr.type","private");
    // 执行查询
    query.findInBackground(newLCIMConversationQueryCallback(){
    @Override
    publicvoiddone(List<LCIMConversation> convs,LCIMException e){
    if(e ==null){
    // convs 就是想要的结果
    }
    }
    });

    LCIMConversationQuery *query =[tom conversationQuery];
    [query whereKey:@"attr.type" equalTo:@"private"];
    // 执行查询
    [query findConversationsWithCallback:^(NSArray *objects, NSError *error){
    NSLog(@"找到 %ld 个对话！",[objects count]);
    }];

    var query = client.getQuery();
    query.equalTo("attr.type","private");
    query
    .find()
    .then(function(conversations){
    // conversations 就是想要的结果
    })
    .catch(console.error.bind(console));

    do{
    let conversationQuery = tom.conversationQuery
    try conversationQuery.where("attr.type",.equalTo("private"))
    try conversationQuery.findConversations {(result)in
    switch result {
    case.success(value:let conversations):
    print(conversations)
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    try{
    ConversationQuery query = jerry.conversationQuery();
      query.whereEqualTo('attr.type','private');
    // conversations 就是想要的结果
    List<Conversation> conversations =await query.find();
    }catch(e){
    print(e);
    }

熟悉数据存储服务的开发者可以更容易理解对话的查询构建，因为对话查询和数据存储服务的对象查询在接口上是十分接近的：

* 可以通过 `find` 获取当前结果页数据
* 支持通过 `count` 获取结果数
* 支持通过 `first` 获取第一个结果
* 支持通过 `skip` 和 `limit` 对结果进行分页

与 `equalTo` 类似，针对 `Number` 和 `Date` 类型的属性还可以使用大于、大于等于、小于、小于等于等，详见下表：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

| 逻辑比较 | `AVIMConversationQuery` 方法 |
| --- | --- |
| 等于 | `WhereEqualTo` |
| 不等于 | `WhereNotEqualsTo` |
| 大于 | `WhereGreaterThan` |
| 大于等于 | `WhereGreaterThanOrEqualsTo` |
| 小于 | `WhereLessThan` |
| 小于等于 | `WhereLessThanOrEqualsTo` |

| 逻辑比较 | `LCIMConversationsQuery` 方法 |
| --- | --- |
| 等于 | `whereEqualTo` |
| 不等于 | `whereNotEqualsTo` |
| 大于 | `whereGreaterThan` |
| 大于等于 | `whereGreaterThanOrEqualsTo` |
| 小于 | `whereLessThan` |
| 小于等于 | `whereLessThanOrEqualsTo` |

| 逻辑比较 | `LCIMConversationQuery` 方法 |
| --- | --- |
| 等于 | `equalTo` |
| 不等于 | `notEqualTo` |
| 大于 | `greaterThan` |
| 大于等于 | `greaterThanOrEqualTo` |
| 小于 | `lessThan` |
| 小于等于 | `lessThanOrEqualTo` |

| 逻辑比较 | `IMConversationQuery` 的 `Constraint` |
| --- | --- |
| 等于 | `equalTo` |
| 不等于 | `notEqualTo` |
| 大于 | `greaterThan` |
| 大于等于 | `greaterThanOrEqualTo` |
| 小于 | `lessThan` |
| 小于等于 | `lessThanOrEqualTo` |

| 逻辑比较 | `ConversationQuery` 方法 |
| --- | --- |
| 等于 | `equalTo` |
| 不等于 | `notEqualTo` |
| 大于 | `greaterThan` |
| 大于等于 | `greaterThanOrEqualTo` |
| 小于 | `lessThan` |
| 小于等于 | `lessThanOrEqualTo` |

使用注意：默认查询条件

为了防止用户无意间拉取到所有的对话数据，在客户端不指定任何 `where` 条件的时候，`ConversationQuery` 会默认查询包含当前用户的对话。如果客户端添加了任一 `where` 条件，那么 `ConversationQuery` 会忽略默认条件而严格按照指定的条件来查询。如果客户端要查询包含某一个 `clientId` 的对话，那么使用下面的 [数组查询](#%E6%95%B0%E7%BB%84%E6%9F%A5%E8%AF%A2) 语法对 `m` 属性列和 `clientId` 值进行查询即可，不会和默认查询条件冲突。

### 正则匹配查询

`ConversationsQuery` 也支持在查询条件中使用正则表达式来匹配数据。比如要查询所有 `language` 是中文的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereMatches("language","[\\u4e00-\\u9fa5]");// language 是中文字符

    query.whereMatches("language","[\\u4e00-\\u9fa5]");// language 是中文字符

    [query whereKey:@"language" matchesRegex:@"[\\u4e00-\\u9fa5]"];// language 是中文字符

    query.matches("language",/[\\u4e00-\\u9fa5]/);// language 是中文字符

    try conversationQuery.where("language",.matchedRegularExpression("[\\u4e00-\\u9fa5]", option:nil))

    // 暂不支持

### 字符串查询

**前缀查询** 类似于 SQL 的 `LIKE 'keyword%'` 条件。例如查询名字以「教育」开头的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereStartsWith("name","教育");

    query.whereStartsWith("name","教育");

    [query whereKey:@"name" hasPrefix:@"教育"];

    query.startsWith("name","教育");

    try conversationQuery.where("name",.prefixedBy("教育"))

    // 暂不支持

**包含查询** 类似于 SQL 的 `LIKE '%keyword%'` 条件。例如查询名字中包含「教育」的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereContains("name","教育");

    query.whereContains("name","教育");

    [query whereKey:@"name" containsString:@"教育"];

    query.contains("name","教育");

    try conversationQuery.where("name",.matchedSubstring("教育"))

    // 暂不支持

**不包含查询** 则可以使用 [正则匹配查询](#%E6%AD%A3%E5%88%99%E5%8C%B9%E9%85%8D%E6%9F%A5%E8%AF%A2) 来实现。例如查询名字中不包含「教育」的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereMatches("name","^((?!教育).)* $ ");

    query.whereMatches("name","^((?!教育).)* $ ");

    [query whereKey:@"name" matchesRegex:@"^((?!教育).)* $ "];

    var regExp =newRegExp("^((?!教育).)*$","i");
    query.matches("name", regExp);

    try conversationQuery.where("name",.matchedRegularExpression("^((?!教育).)* $ ", option:nil))

    // 暂不支持

### 数组查询

可以使用 `containsAll`、`containedIn`、`notContainedIn` 来对数组进行查询。例如查询成员中包含「Tom」的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var members =newList<string>{"Tom"};
    query.WhereContainedIn("m", members);

    query.whereContainedIn("m",Arrays.asList("Tom"));

    [query whereKey:@"m" containedIn:@[@"Tom"]];

    query.containedIn("m",["Tom"]);

    try conversationQuery.where("m",.containedIn(["Tom"]))

    // 暂不支持

### 空值查询

空值查询是指查询相关列是否为空值的方法，例如要查询 `lm` 列为空值的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereDoesNotExist("lm");

    query.whereDoesNotExist("lm");

    [query whereKeyDoesNotExist:@"lm"];

    query.doesNotExist("lm");

    try conversationQuery.where("lm",.notExisted)

    // 暂不支持

反过来，如果要查询 `lm` 列不为空的对话，则替换为如下条件即可：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereExists("lm");

    query.whereExists("lm");

    [query whereKeyExists:@"lm"];

    query.exists("lm");

    try conversationQuery.where("lm",.existed)

    // 暂不支持

**注意，系统消息（服务号）没有 lm 列，可以替换为 updatedAt。**

### 组合查询

查询年龄小于 18 岁，并且关键字包含「教育」的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WhereContains("keywords","教育")
    .WhereLessThan("age",18);

    query.whereContains("keywords","教育");
    query.whereLessThan("age",18);

    [query whereKey:@"keywords" containsString:@"教育"];
    [query whereKey:@"age" lessThan:@(18)];

    query.contains("keywords","教育").lessThan("age",18);

    try conversationQuery.where("keywords",.matchedSubstring("教育"))
    try conversationQuery.where("age",.lessThan(18))

    // 暂不支持

另外一种组合的方式是，两个查询采用 `or` 或者 `and` 的方式构建一个新的查询。

查询年龄小于 18 或者关键字包含「教育」的对话：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // 暂不支持

    LCIMConversationsQuery ageQuery = tom.getConversationsQuery();
    ageQuery.whereLessThan('age',18);

    LCIMConversationsQuery keywordsQuery = tom.getConversationsQuery();
    keywordsQuery.whereContains('keywords', '教育');

    LCIMConversationsQuery query =LCIMConversationsQuery.or(Arrays.asList(priorityQuery, statusQuery));

    LCIMConversationQuery *ageQuery =[tom conversationQuery];
    [ageQuery whereKey:@"age" greaterThan:@(18)];

    LCIMConversationQuery *keywordsQuery =[tom conversationQuery];
    [keywordsQuery whereKey:@"keywords" containsString:@"教育"];

    LCIMConversationQuery *query =[LCIMConversationQuery orQueryWithSubqueries:[NSArray arrayWithObjects:ageQuery,keywordsQuery,nil]];

    // JavaScript SDK 暂不支持

    do{
    let ageQuery = tom.conversationQuery
    try ageQuery.where("age",.greaterThan(18))

    let keywordsQuery = tom.conversationQuery
    try keywordsQuery.where("keywords",.matchedSubstring("教育"))

    let conversationQuery =try ageQuery.or(keywordsQuery)
    }catch{
    print(error)
    }

    // 暂不支持

### 结果排序

可以指定查询结果按照部分属性值的升序或降序来返回。例如：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.OrderByDescending("createdAt");

    query.orderByDescending("createdAt");

    [query orderByDescending:@"createdAt"];

    // 对查询结果按照 name 升序，然后按照创建时间降序排序
    query.addAscending("name").addDescending("createdAt");

    try conversationQuery.where("createdAt",.descending)

    // 暂不支持

### 不带成员信息的精简模式

普通对话最多可以容纳 500 个成员，在有些业务逻辑不需要对话的成员列表的情况下，可以使用「精简模式」进行查询，这样返回结果中不会包含成员列表（`members` 字段为空数组），有助于提升应用的性能同时减少流量消耗。

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.Compact =true;

    query.setCompact(true);

    query.option = LCIMConversationQueryOptionCompact;

    query.compact(true);

    conversationQuery.options =[.notContainMembers]

    query.excludeMembers =true;

### 让查询结果附带一条最新消息

对于一个聊天应用，一个典型的需求是在对话的列表界面显示最后一条消息，默认情况下，针对对话的查询结果是不带最后一条消息的，需要单独打开相关选项：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    query.WithLastMessageRefreshed =true;

    query.setWithLastMessagesRefreshed(true);

    query.option = LCIMConversationQueryOptionWithMessage;

    // withLastMessagesRefreshed 方法可以指定让查询结果带上最后一条消息
    query.withLastMessagesRefreshed(true);

    conversationQuery.options =[.containLastMessage]

    query.includeLastMessage =true;

需要注意的是，这个选项真正的意义是「刷新对话的最后一条消息」，这意味着由于 SDK 缓存机制的存在，将这个选项设置为 `false` 查询得到的对话也还是有可能会存在最后一条消息的。

### 查询缓存

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

.NET SDK 暂不支持缓存功能。

通常，将查询结果缓存到磁盘上是一种行之有效的方法，这样就算设备离线，应用刚刚打开，网络请求尚未完成时，数据也能显示出来。或者为了节省用户流量，在应用打开的第一次查询走网络，之后的查询可优先走本地缓存。

值得注意的是，默认的策略是先走本地缓存的再走网络的，缓存时间是一小时。`LCIMConversationsQuery` 中有如下方法：

    // 设置 LCIMConversationsQuery 的查询策略
    publicvoidsetQueryPolicy(LCQuery.CachePolicy policy);

有时你希望先走网络查询，发生网络错误的时候，再从本地查询，可以这样：

    LCIMConversationsQuery query = client.getConversationsQuery();
    query.setQueryPolicy(LCQuery.CachePolicy.NETWORK_ELSE_CACHE);
    query.findInBackground(newLCIMConversationQueryCallback(){
    @Override
    publicvoiddone(List<LCIMConversation> conversations,LCIMException e){

    }
    });

通常，将查询结果缓存到磁盘上是一种行之有效的方法，这样就算设备离线，应用刚刚打开，网络请求尚未完成时，数据也能显示出来。或者为了节省用户流量，在应用打开的第一次查询走网络，之后的查询可优先走本地缓存。

值得注意的是，默认的策略是先走本地缓存的再走网络的，缓存时间是一小时。`LCIMConversationQuery` 中有如下方法：

    // 设置缓存策略，默认是 kLCCachePolicyCacheElseNetwork
    @property(nonatomic) LCCachePolicy cachePolicy;

    // 设置缓存的过期时间，默认是 1 小时（1 * 60 * 60）
    @property(nonatomic) NSTimeInterval cacheMaxAge;

有时你希望先走网络查询，发生网络错误的时候，再从本地查询，可以这样：

    LCIMConversationQuery *query =[client conversationQuery];
    query.cachePolicy = kLCCachePolicyNetworkElseCache;
    [query findConversationsWithCallback:^(NSArray *objects, NSError *error){

    }];

各种查询缓存策略的行为可以参考[数据存储指南](../../storage/guide/dotnet/)的《缓存查询》一节。

JavaScript SDK 会对按照对话 ID 对对话进行内存字典缓存，但不会进行持久化的缓存。

Swift SDK 提供了会话的缓存功能，包括内存缓存和持久化缓存。

会话的内存缓存：

    client.getCachedConversation(ID:"CONVERSATION_ID"){(result)in
    switch result {
    case.success(value:let conversation):
    print(conversation)
    case.failure(error:let error):
    print(error)
    }
    }

    client.removeCachedConversation(IDs:["CONVERSATION_ID"]){(result)in
    switch result {
    case.success:
    break
        case.failure(error:let error):
    print(error)
    }
    }

会话的持久化缓存。**注意，使用「查询持久存储会话」以及「删除持久存储会话」的功能前，需调用`prepareLocalStorage` 方法且回调结果为成功；`prepareLocalStorage` 方法只需要调用一次（返回成功），一般在 `IMClient.init()` 和 `IMClient.open()` 之间调用**：

    // Switch for Local Storage of IM Client
    do{
    // Client init with Local Storage feature
    let clientWithLocalStorage =tryIMClient(ID:"CLIENT_ID")

    // Client init without Local Storage feature
    var options =IMClient.Options.default
        options.remove(.usingLocalStorage)
    let clientWithoutLocalStorage =tryIMClient(ID:"CLIENT_ID", options: options)
    }catch{
    print(error)
    }

    // Preparation for Local Storage of IM Client
    do{
    try client.prepareLocalStorage {(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    // Get and Load Stored Conversations to Memory
    do{
    try client.getAndLoadStoredConversations(completion:{(result)in
    switch result {
    case.success(value:let conversations):
    print(conversations)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    // Delete Stored Conversations and Messages belong to them
    do{
    try client.deleteStoredConversationAndMessages(IDs:["CONVERSATION_ID"], completion:{(result)in
    switch result {
    case.success:
    break
            case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

注意：

  1. 聊天室和临时会话没有本地缓存机制。
  2. 会话有内存缓存和持久化（磁盘）缓存。消息只有持久化缓存，且只支持消息查询的结果（查询结果小于 3 时不缓存）。

Flutter SDK 暂不支持缓存功能。

### 性能优化建议

`Conversation` 数据是存储在云端数据库中的，与存储服务中的对象查询类似，我们需要尽可能利用索引来提升查询效率，这里有一些优化查询的建议：

* `Conversation` 的 `objectId`、`updatedAt`、`createdAt` 等属性上是默认建了索引的，所以通过这些条件来查询会比较快。
* 虽然 `skip` 搭配 `limit` 的方式可以翻页，但是在结果集较大的时候不建议使用，因为数据库端计算翻页距离是一个非常低效的操作，取而代之的是尽量通过 `updatedAt` 或 `lastMessageAt` 等属性来限定返回结果集大小，并以此进行翻页。
* 使用 `m` 列的 `contains` 查询来查找包含某人的对话时，也尽量使用默认的 `limit` 大小 10，再配合 `updatedAt` 或者 `lastMessageAt` 来做条件约束，性能会提升较大。
* 整个应用对话如果数量太多，可以考虑在云引擎封装一个云函数，用定时任务启动之后，周期性地做一些清理，例如可以归档或删除一些不活跃的对话。

## 聊天记录查询

消息记录默认会在云端保存 **180** 天，开发者可以通过额外付费来延长这一期限（有需要的用户请提工单联系技术支持），也可以通过 REST API 将聊天记录同步到自己的服务器上。

SDK 提供了多种方式来拉取历史记录，iOS 和 Android SDK 还提供了内置的消息缓存机制，以减少客户端对云端消息记录的查询次数，并且在设备离线情况下，也能展示出部分数据保障产品体验不会中断。

### 从新到旧获取对话的消息记录

在终端用户进入一个对话的时候，最常见的需求就是由新到旧、以翻页的方式拉取并展示历史消息，这可以通过如下代码实现：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // limit 取值范围 1~100，默认 20
    var messages =await conversation.QueryMessages(limit:10);
    foreach(var message in messages){
    if(message isLCIMTextMessage textMessage){

    }
    }

    // limit 取值范围 1~100，如调用 queryMessages 时不带 limit 参数，默认获取 20 条消息记录
    int limit =10;
    conv.queryMessages(limit,newLCIMMessagesQueryCallback(){
    @Override
    publicvoiddone(List<LCIMMessage> messages,LCIMException e){
    if(e ==null){
    // 成功获取最新 10 条消息记录
    }
    }
    });

    // 查询对话中最后 10 条消息，limit 取值范围 1~100，值为 0 时获取 20 条消息记录（使用服务端默认值）
    [conversation queryMessagesWithLimit:10 callback:^(NSArray *objects, NSError *error){
    NSLog(@"查询成功！");
    }];

    conversation
    .queryMessages({
    limit:10,// limit 取值范围 1~100，默认 20
    })
    .then(function(messages){
    // 最新的十条消息，按时间增序排列
    })
    .catch(console.error.bind(console));

    do{
    try conversation.queryMessage(limit:10){(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    }
    }catch{
    print(error)
    }

    // limit 取值范围 1~100，如调用 queryMessage 时不带 limit 参数，默认获取 20 条消息记录
    try{
    List<Message> messages =await conversation.queryMessage(
        limit:10,
    );
    }catch(e){
    print(e);
    }

`queryMessage` 接口也是支持翻页的。即时通讯云端通过消息的 `messageId` 和发送时间戳来唯一定位一条消息，因此要从某条消息起拉取后续的 N 条记录，只需要指定起始消息的 `messageId` 和发送时间戳作为锚定就可以了，示例代码如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // limit 取值范围 1~1000，默认 100
    var messages =await conversation.QueryMessages(limit:10);
    var oldestMessage = messages[0];
    var start =newLCIMMessageQueryEndpoint{
        MessageId = oldestMessage.Id,
        SentTimestamp = oldestMessage.SentTimestamp
    };
    var messagesInPage =await conversation.QueryMessages(start: start);

    // limit 取值范围 1~1000，默认 100
    conv.queryMessages(10,newLCIMMessagesQueryCallback(){
    @Override
    publicvoiddone(List<LCIMMessage> messages,LCIMException e){
    if(e ==null){
    // 成功获取最新 10 条消息记录
    // 返回的消息一定是时间增序排列，也就是最早的消息一定是第一个
    LCIMMessage oldestMessage = messages.get(0);

          conv.queryMessages(oldestMessage.getMessageId(), oldestMessage.getTimestamp(),20,
    newLCIMMessagesQueryCallback(){
    @Override
    publicvoiddone(List<LCIMMessage> messagesInPage,LCIMException e){
    if(e==null){
    // 查询成功返回
    Log.d("Tom & Jerry","got "+ messagesInPage.size()+" messages");
    }
    }
    });
    }
    }
    });

    // 查询对话中最后 10 条消息
    [conversation queryMessagesWithLimit:10 callback:^(NSArray *messages, NSError *error){
    NSLog(@"第一次查询成功！");
    // 以第一页的最早的消息作为开始，继续向前拉取消息
        LCIMMessage *oldestMessage =[messages firstObject];
    [conversation queryMessagesBeforeId:oldestMessage.messageId timestamp:oldestMessage.sendTimestamp limit:10 callback:^(NSArray *messagesInPage, NSError *error){
    NSLog(@"第二次查询成功！");
    }];
    }];

    // JS SDK 通过迭代器隐藏了翻页的实现细节，开发者通过不断的调用 next 方法即可获得后续数据。
    // 创建一个迭代器，每次获取 10 条历史消息
    var messageIterator = conversation.createMessagesIterator({limit:10});
    // 第一次调用 next 方法，获得前 10 条消息，还有更多消息，done 为 false
    messageIterator
    .next()
    .then(function(result){
    // result: {
    //   value: [message1, ..., message10],
    //   done: false,
    // }
    })
    .catch(console.error.bind(console));
    // 第二次调用 next 方法，获得第 11~20 条消息，还有更多消息，done 为 false
    // 迭代器内部会记录起始消息的数据，无需开发者显示指定
    messageIterator
    .next()
    .then(function(result){
    // result: {
    //   value: [message11, ..., message20],
    //   done: false,
    // }
    })
    .catch(console.error.bind(console));

    do{
    let start =IMConversation.MessageQueryEndpoint(
            messageID:"MESSAGE_ID",
            sentTimestamp:31415926,
            isClosed:false
    )
    try conversation.queryMessage(start: start, limit:10, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    List<Message> messages;
    try{
    // 第一次查询成功
      messages =await conversation.queryMessage(
        limit:10,
    );
    }catch(e){
    print(e);
    }

    try{
    // 返回的消息一定是时间增序排列，也就是最早的消息一定是第一个
    Message oldMessage = messages.first;
    // 以第一页的最早的消息作为开始，继续向前拉取消息
    List<Message> messages2 =await conversation.queryMessage(
        startTimestamp: oldMessage.sentTimestamp,
        startMessageID: oldMessage.id,
        startClosed:true,
        limit:10,
    );
    }catch(e){
    print(e);
    }

### 按照消息类型获取

除了按照时间先后顺序拉取历史消息之外，即时通讯服务云端也支持按照消息的类型来拉取历史消息，这一功能可能对某些产品来说非常有用，例如我们需要展现某一个聊天群组里面所有的图像。

`queryMessage` 接口还支持指定特殊的消息类型，其示例代码如下：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // 传入泛型参数，SDK 会自动读取类型的信息发送给服务端，用作筛选目标类型的消息
    var imageMessages =await conversation.QueryMessages(messageType:-2);

    int msgType =LCIMMessageType.IMAGE_MESSAGE_TYPE;
    conversation.queryMessagesByType(msgType, limit,newLCIMMessagesQueryCallback(){
    @Override
    publicvoiddone(List<LCIMMessage> messages,LCIMException e){
    }
    });

    [conversation queryMediaMessagesFromServerWithType:LCIMMessageMediaTypeImage limit:10 fromMessageId:nil fromTimestamp:0 callback:^(NSArray *messages, NSError *error){
    if(!error){
    NSLog(@"查询成功！");
    }
    }];

    conversation
    .queryMessages({type:ImageMessage.TYPE})
    .then((messages)=>{
    console.log(messages);
    })
    .catch(console.error);

    do{
    try conversation.queryMessage(limit:10, type:IMTextMessage.messageType, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    List<Message> messages =await conversation.queryMessage(type:-2);
    }catch(e){
    print(e);
    }

如要获取更多图像消息，可以效仿前一章节中的示例代码，继续翻页查询即可。

### 从旧到新反向获取历史消息

即时通讯云端支持的历史消息查询方式是非常多的，除了上面列举的两个最常见需求之外，还可以支持按照由旧到新的方向进行查询。如下代码演示从对话创建的时间点开始，从前往后查询消息记录：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var earliestMessages =await conversation.QueryMessages(direction: LCIMMessageQueryDirection.OldToNew);

    LCIMMessageInterval interval =newLCIMMessageInterval(null,null);
    conversation.queryMessages(interval,DirectionFromOldToNew, limit,
    newLCIMMessagesQueryCallback(){
    publicvoiddone(List<LCIMMessage> messages,LCIMException exception){
    // 处理结果
    }
    });

    [conversation queryMessagesInInterval:nil direction:LCIMMessageQueryDirectionFromOldToNew limit:20 callback:^(NSArray<LCIMMessage *>* _Nullable messages, NSError * _Nullable error){
    if(messages.count){
    // 处理结果
    }
    }];

    var{MessageQueryDirection}=require('leancloud-realtime');
    conversation.queryMessages({
    direction:MessageQueryDirection.OLD_TO_NEW,
    }).then(function(messages){
    // 处理结果
    }.catch(function(error){
    // 处理异常
    });

    do{
    try conversation.queryMessage(direction:.oldToNew, limit:10, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    List<Message> messages =await conversation.queryMessage(
        direction:MessageQueryDirection.oldToNew,
    );
    }catch(e){
    print(e);
    }

这种情况下要实现翻页，接口会稍微复杂一点，请继续阅读下一节。

### 从某一时间戳往某一方向查询

即时通讯服务云端支持以某一条消息的 ID 和时间戳为准，往一个方向查：

* 从新到旧：以某一条消息为基准，查询它 **之前** 产生的消息
* 从旧到新：以某一条消息为基准，查询它 **之后** 产生的消息

这样我们就可以在不同方向上实现消息翻页了。

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var earliestMessages =await conversation.QueryMessages(direction: LCIMMessageQueryDirection.OldToNew,limit:1);
    // 获取 earliestMessages.Last() 之后的消息
    var lastMessage = earliestMessages.Last();
    var start =newLCIMMessageQueryEndpoint{
        MessageId = lastMessage.Id,
        SentTimestamp = lastMessage.SentTimestamp
    };
    var nextPageMessages =await conversation.QueryMessages(start: start);

    LCIMMessageIntervalBound start =LCIMMessageInterval.createBound(messageId, timestamp,false);
    LCIMMessageInterval interval =newLCIMMessageInterval(start,null);
    LCIMMessageQueryDirection direction;
    conversation.queryMessages(interval, direction, limit,
    newLCIMMessagesQueryCallback(){
    publicvoiddone(List<LCIMMessage> messages,LCIMException exception){
    // 处理结果
    }
    });

    LCIMMessageIntervalBound *start =[[LCIMMessageIntervalBound alloc] initWithMessageId:nil timestamp:timestamp closed:false];
    LCIMMessageInterval *interval =[[LCIMMessageInterval alloc] initWithStartIntervalBound:start endIntervalBound:nil];
    [conversation queryMessagesInInterval:interval direction:direction limit:20 callback:^(NSArray<LCIMMessage *>* _Nullable messages, NSError * _Nullable error){
    if(messages.count){
    // 处理结果
    }
    }];

    var{MessageQueryDirection}=require('leancloud-realtime');
    conversation.queryMessages({
    startTime: timestamp,
    startMessageId: messageId,
    startClosed:false,
    direction:MessageQueryDirection.OLD_TO_NEW,
    }).then(function(messages){
    // 处理结果
    }.catch(function(error){
    // 处理异常
    });

    do{
    let start =IMConversation.MessageQueryEndpoint(
            messageID:"MESSAGE_ID",
            sentTimestamp:31415926,
            isClosed:true
    )
    try conversation.queryMessage(start: start, direction:.oldToNew, limit:10, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    List<Message> messages =await conversation.queryMessage(
        startTimestamp: textMessage.sentTimestamp,
        startMessageID: textMessage.id,
        startClosed:true,
        direction:MessageQueryDirection.oldToNew,
        limit:10,
    );
    }catch(e){
    print(e);
    }

### 获取指定区间内的消息

除了顺序查找之外，我们也支持获取特定时间区间内的消息。假设已知 2 条消息，这 2 条消息以较早的一条为起始点，而较晚的一条为终点，这个区间内产生的消息可以用如下方式查询：

注意：**每次查询也有 100 条限制，如果想要查询区间内所有产生的消息，替换区间起始点的参数即可。**

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    var earliestMessage =await conversation.QueryMessages(direction: LCIMMessageQueryDirection.OldToNew,limit:1);
    var latestMessage =await conversation.QueryMessages(limit:1);
    var start =newLCIMMessageQueryEndpoint{
        MessageId = earliestMessage[0].Id
    };
    var end =newLCIMMessageQueryEndpoint{
        MessageId = latestMessage[0].Id
    };
    // messagesInInterval 最多可包含 100 条消息
    var messagesInInterval =await conversation.QueryMessages(start: start,end: end);

    LCIMMessageIntervalBound start =LCIMMessageInterval.createBound(messageId, timestamp,false);
    LCIMMessageIntervalBound end =LCIMMessageInterval.createBound(endMessageId, endTimestamp,false);
    LCIMMessageInterval interval =newLCIMMessageInterval(start, end);
    LCIMMessageQueryDirection direction;
    conversation.queryMessages(interval, direction, limit,
    newLCIMMessagesQueryCallback(){
    publicvoiddone(List<LCIMMessage> messages,LCIMException exception){
    // 处理结果
    }
    });

    LCIMMessageIntervalBound *start =[[LCIMMessageIntervalBound alloc] initWithMessageId:nil timestamp:startTimestamp closed:false];
    LCIMMessageIntervalBound *end =[[LCIMMessageIntervalBound alloc] initWithMessageId:nil timestamp:endTimestamp closed:false];
    LCIMMessageInterval *interval =[[LCIMMessageInterval alloc] initWithStartIntervalBound:start endIntervalBound:end];
    [conversation queryMessagesInInterval:interval direction:direction limit:100 callback:^(NSArray<LCIMMessage *>* _Nullable messages, NSError * _Nullable error){
    if(messages.count){
    // 处理结果
    }
    }];

    conversation.queryMessages({
    startTime: timestamp,
    startMessageId: messageId,
    endTime: endTimestamp,
    endMessageId: endMessageId,
    }).then(function(messages){
    // 处理结果
    }.catch(function(error){
    // 处理异常
    });

    do{
    let start =IMConversation.MessageQueryEndpoint(
            messageID:"MESSAGE_ID_1",
            sentTimestamp:31415926,
            isClosed:true
    )
    let end =IMConversation.MessageQueryEndpoint(
            messageID:"MESSAGE_ID_2",
            sentTimestamp:31415900,
            isClosed:true
    )
    try conversation.queryMessage(start: start, end: end, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    try{
    List<Message> messages =await conversation.queryMessage(
        startTimestamp: textMessage.sentTimestamp,
        startMessageID: textMessage.id,
        startClosed:true,
        endTimestamp: fileMessage.sentTimestamp,
        endMessageID: fileMessage.id,
        endClosed:true,
    );
    }catch(e){
    print(e);
    }

### 客户端消息缓存

iOS 和 Android SDK 针对移动设备的特殊性，实现了客户端消息的缓存。开发者无需进行特殊设置，只要接收或者查询到的新消息，默认都会进入被缓存起来，该机制给开发者提供了如下便利：

  1. 客户端可以在未联网的情况下进入对话列表之后，可以获取聊天记录，提升用户体验
  2. 减少查询的次数和流量的消耗
  3. 极大地提升了消息记录的查询速度和性能

客户端缓存是默认开启的，如果开发者有特殊的需求，SDK 也支持关闭缓存功能。例如有些产品在应用层进行了统一的消息缓存，无需 SDK 层再进行冗余存储，可以通过如下接口来关闭消息缓存：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    // 暂不支持

    // 需要在调用 LCIMClient.open(callback) 函数之前设置，关闭历史消息缓存开关。
    LCIMOptions.getGlobalOptions().setMessageQueryCacheEnabled(false);

    // 需要在调用 [avimClient openWithCallback:callback] 函数之前设置，关闭历史消息缓存开关。
    avimClient.messageQueryCacheEnabled = false;

    // 暂不支持

    // Switch for Local Storage of IM Client
    do{
    // Client init with Local Storage feature
    let clientWithLocalStorage =tryIMClient(ID:"CLIENT_ID")

    // Client init without Local Storage feature
    var options =IMClient.Options.default
        options.remove(.usingLocalStorage)
    let clientWithoutLocalStorage =tryIMClient(ID:"CLIENT_ID", options: options)
    }catch{
    print(error)
    }

    // Message Query Policy
    enumMessageQueryPolicy{
    case `default`
    case onlyNetwork
    case onlyCache
    case cacheThenNetwork
    }

    do{
    try conversation.queryMessage(policy:.default, completion:{(result)in
    switch result {
    case.success(value:let messages):
    print(messages)
    case.failure(error:let error):
    print(error)
    }
    })
    }catch{
    print(error)
    }

    // 暂不支持

## 用户退出与网络状态变化

### 用户退出即时通讯服务

如果产品层面设计了用户退出登录或者切换账号的接口，对于即时通讯服务来说，也是需要完全注销当前用户的登录状态的。在 SDK 中，开发者可以通过调用 `LCIMClient` 的 `close` 系列方法完成即时通讯服务的「退出」：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

    await tom.Close();

    tom.close(newLCIMClientCallback(){
    @Override
    publicvoiddone(LCIMClient client,LCIMException e){
    if(e==null){
    // 登出成功
    }
    }
    });

    [tom closeWithCallback:^(BOOL succeeded, NSError * _Nullable error){
    if(succeeded){
    NSLog(@"退出即时通讯服务");
    }
    }];

    tom
    .close()
    .then(function(){
    console.log("Tom 退出登录");
    })
    .catch(console.error.bind(console));

    tom.close {(result)in
    switch result {
    case.success:
    break
        case.failure(error:let error):
    print(error)
    }
    }

    await tom.close();

调用该接口之后，客户端就与即时通讯服务云端断开连接了，从云端查询前一 `clientId` 的状态，会显示「离线」状态。

### 客户端事件与网络状态响应

即时通讯服务与终端设备的网络连接状态休戚相关，如果网络中断，那么所有的消息收发和对话操作都会失败，这时候产品层面需要在 UI 上给予用户足够的提示，以免影响使用体验。

我们的 SDK 内部和即时通讯云端会维持一个「心跳」机制，能够及时感知到客户端的网络变化，同时将底层网络变化事件通知到应用层。具体来讲，当网络连接出现中断、恢复等状态变化时，SDK 会派发以下事件：

* C#
* Java
* Objective-C
* JavaScript
* Swift
* Flutter

`LCIMClient` 上会有如下事件通知：

* `OnPaused` 指网络连接断开事件发生，此时聊天服务不可用
* `OnResume` 指网络连接恢复正常，此时聊天服务变得可用
* `OnClose` 指连接关闭，且不会自动重连

`LCIMClientEventHandler` 上会有如下事件通知：

* `onConnectionPaused()` 指网络连接断开事件发生，此时聊天服务不可用。
* `onConnectionResume()` 指网络连接恢复正常，此时聊天服务变得可用。
* `onClientOffline()` 指单点登录被踢下线的事件。

在 `LCIMClientDelegate` 里，可以接收到如下所示的事件通知：

* `imClientResumed`：连接自动恢复了
* `imClientPaused`：连接断开了；该事件被触发的常见场景：网络无法访问、应用进入后台
* `imClientResuming`：正在重新建立连接
* `imClientClosed`：连接关闭，且不会自动重连；该事件被触发的常见场景：单设备登录冲突、后台主动把该 client 下线

    -(void)imClientResumed:(LCIMClient *)imClient
    {

    }

    -(void)imClientResuming:(LCIMClient *)imClient
    {

    }

    -(void)imClientPaused:(LCIMClient *)imClient error:(NSError * _Nullable)error
    {

    }

    -(void)imClientClosed:(LCIMClient *)imClient error:(NSError * _Nullable)error
    {

    }

* `DISCONNECT`：与服务端连接断开，此时聊天服务不可用。
* `OFFLINE`：网络不可用。
* `ONLINE`：网络恢复。
* `SCHEDULE`：计划在一段时间后尝试重连，此时聊天服务仍不可用。
* `RETRY`：正在重连。
* `RECONNECT`：与服务端连接恢复，此时聊天服务可用。

    var{Event}=require("leancloud-realtime");

    realtime.on(Event.DISCONNECT,function(){
    console.log("服务器连接已断开");
    });
    realtime.on(Event.OFFLINE,function(){
    console.log("离线（网络连接已断开）");
    });
    realtime.on(Event.ONLINE,function(){
    console.log("已恢复在线");
    });
    realtime.on(Event.SCHEDULE,function(attempt, delay){
    console.log(delay +" ms 后进行第 "+(attempt +1)+" 次重连");
    });
    realtime.on(Event.RETRY,function(attempt){
    console.log("正在进行第 "+(attempt +1)+" 次重连");
    });
    realtime.on(Event.RECONNECT,function(){
    console.log("与服务端连接恢复");
    });

在 `IMClientDelegate` 的 `IMClientDelegate.client(_:event:)` 函数里，可以接收到如下所示的事件通知：

* `sessionDidOpen`：连接自动恢复了
* `sessionDidPause`：连接断开了；该事件被触发的常见场景：网络无法访问、应用进入后台
* `sessionDidResume`：正在重新建立连接
* `sessionDidClose`：连接关闭，且不会自动重连；该事件被触发的常见场景：单设备登录冲突、后台主动把该 client 下线

    funcclient(_ client:IMClient, event:IMClientEvent){
    switch event {
    case.sessionDidOpen:
    break
        case.sessionDidPause(error:let error):
    print(error)
    case.sessionDidResume:
    break
        case.sessionDidClose(error:let error):
    print(error)
    }
    }

`Client` 有如下事件通知：

* `onOpened` 用户登录即时通信的服务。
* `onClosed` 用户退出即时通信服务。
* `onResuming` 指网络正在尝试重连，此时聊天服务不可用。
* `onDisconnected` 指网络连接断开事件发生，此时聊天服务不可用。

## 其他开发建议

### 如何根据活跃度来展示对话列表

不管是当前用户参与的「对话」列表，还是全局热门的开放聊天室列表展示出来了，我们下一步要考虑的就是如何把最活跃的对话展示在前面，这里我们把「活跃」定义为最近有新消息发出来。我们希望有最新消息的对话可以展示在对话列表的最前面，甚至可以把最新的那条消息也附带显示出来，这时候该怎么实现呢？

我们专门为 `LCIMConversation` 增加了一个动态的属性 `lastMessageAt`（对应 `_Conversation` 表里的 `lm` 字段），记录了对话中最后一条消息到达即时通讯云端的时间戳，这一数字是服务器端的时间（精确到秒），所以不用担心客户端时间对结果造成影响。另外，`LCIMConversation` 还提供了一个方法可以直接获取最新的一条消息。这样在界面展现的时候，开发者就可以自己决定展示内容与顺序了。

### 自动重连

如果开发者没有明确调用退出登录的接口，但是客户端网络存在抖动或者切换（对于移动网络来说，这是比较常见的情况），我们 iOS 和 Android SDK 默认内置了断线重连的功能，会在网络恢复的时候自动建立连接，此时 `IMClient` 的网络状态可以通过底层的网络状态响应接口得到回调。

### 更多「对话」类型

即时通讯服务提供的功能就是让一个客户端与其他客户端进行在线的消息互发，对应不同的使用场景，除了前两章节介绍的 [一对一单聊](#%E4%B8%80%E5%AF%B9%E4%B8%80%E5%8D%95%E8%81%8A) 和 [多人群聊](#%E5%A4%9A%E4%BA%BA%E7%BE%A4%E8%81%8A) 之外，我们也支持其他形式的「对话」模型：

* 开放聊天室，例如直播中的弹幕聊天室，它与普通的「多人群聊」的主要差别是允许的成员人数以及消息到达的保证程度不一样。有兴趣的开发者可以参考[即时通讯开发指南第三篇](senior/)的《玩转直播聊天室》一节。

* 临时对话，例如客服系统中用户和客服人员之间建立的临时通道，它与普通的「一对一单聊」的主要差别在于对话总是临时创建并且不会长期存在，在提升实现便利性的同时，还能降低服务使用成本（能有效减少存储空间方面的花费）。有兴趣的开发者可以参考[即时通讯开发指南第三篇](senior/)的《使用临时对话》一节。

* 系统对话，例如在微信里面常见的公众号／服务号，系统全局的广播账号，与普通「多人群聊」的主要差别，在于「服务号」是以订阅的形式加入的，也没有成员限制，并且订阅用户和服务号的消息交互是一对一的，一个用户的上行消息不会群发给其他订阅用户。有兴趣的开发者可以参考[即时通讯开发指南第四篇](systemconv/)《「系统对话」的使用》一节。

## 进一步阅读

* 《即时通讯开发指南》第二篇[消息收发的更多方式，离线推送与消息同步，多设备登录](intermediate/)
* 《即时通讯开发指南》第三篇[安全与签名、玩转聊天室和临时对话](senior/)
* 《即时通讯开发指南》第四篇[详解消息 hook 与系统对话](systemconv/)
