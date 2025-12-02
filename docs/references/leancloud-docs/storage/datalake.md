# 数据仓库使用指南

基于现代的数据库 ClickHouse ，我们构建了新一代的数据仓库。与云服务紧密集成，支持将存储数据，日志表数据自动入库，从而为业务运营的统计分析提供强大的数据支持。

新的数据仓库将提供以下独特的功能：

  1. 基于列的存储，支持高比率的压缩，可以大幅度缩减存储成本；
  2. 基于列的遍历和向量的运算支持高效的查询效率，可以将原本需要分钟级别的复杂查询，缩短到秒级别；
  3. 直观的数据视图功能，支持存储中间结果，配合 join 查询，可支持高效率且复杂的二阶查询；
  4. 更多样的函数，支持更复杂的 SQL 查询，可参考下述「[常见用例](#%E5%B8%B8%E8%A7%81%E7%94%A8%E4%BE%8B%E6%8E%A8%E8%8D%90)」小节；
  5. 无缝对接日志表，可支持多样的数据源实时入库和查询，从而更灵活地集成外部数据源，为业务提供更完备的数据分析能力。

## 数据入库

在对数据进行查询前，我们首先需要将数据入库。目前，我们主要支持数据存储 Class 的入库。数据存储 Class 又具体分为两类，一类是日志表，另一类则是普通 Class 。

### 日志表

日志表是数据存储中的一类特殊表，是为了满足业务存储事件，日志等「不变型」数据的需求而设计，这类数据的特点是写入之后不会再修改。这些数据在被收集起来之后，可以应用于业务审计与运营分析，开发者对事件进行追踪等场景。由于该类数据只有追加，没有修改，我们能够提供更大的并发吞吐写入。

#### 开启和接入日志表

在控制台「数据存储」页面，点击创建 Class ，勾选「日志表」选项即可创建日志表。比如我们可以创建一个名为 `EventLog` 的日志表。

在 SDK 层面，日志表对象的创建与普通对象的创建一致：

    // for Android
    AVObject event =newAVObject("EventLog");
    event.put("eventType","buttonClick");
    event.put("eventName","orderSubmit");
    event.put("eventDate",newDate());
    event.saveInBackground();

日志提交后会直接入库数据仓库，并且实时可查。

### 普通 Class 的同步

普通 Class 对象，由于支持更新，同步到数据仓库的流程要稍微复杂一些。

在控制台「数据存储」-「数据仓库」中，点击创建 Class 同步，选择需要在数据仓库中查询分析的字段，即可开启 Class 到数据仓库的同步。存量数据会即刻开始同步，取决于数据量的大小，同步可能持续较长时间，请耐心等待。

开启同步的 Class ，我们会在次日凌晨同步前一日更新过的数据。因此更新的对象需要在次日才可见。我们还会持续优化该流程，以期实现更实时的同步。

### 数据类型的转换

数据仓库中的字段类型与存储有着显著的差异，在数据入库的过程中我们会进行数据转换。其中需要特别注意的是，

  1. 数据仓库不支持 `null` 类型，对于字段缺失的情况以零值存储。字符类型的零值是空字符串，数字字段的零值则是数值 0。
  2. `Boolean` 类型会被转换为 `UInt8` 存储。0 值表示 false, 1 表示 true 。加之上述零值特性，默认缺失值为 0 表示 false 。
  3. 不支持嵌套的 `Object` 类型，实际会以 JSON 字符串的形式存储，使用时需要使用 JSON 函数来提取。
  4. 对于数组类型，要求元素是同一类型。在入库的过程中会转换成 `Array(String)`，使用时需要用类型转换函数转换回原类型。

具体的类型转换说明见下表：

| 存储类型 | 数据仓库类型 | 转换说明 | 使用示例 |
| --- | --- | --- | --- |
| Array | Array(String) | 元素类型会以字符存储，在提取元素后需要使用类型转换回原始类型 | `toInt64(xs[1])` |
| Boolean | UInt8 | 0 表示 false, 1 表示 true | `emailVerified = 1` |
| Bytes | N/A | 不支持 |
| Date | DateTime |
| File | `*.className String` |
| `*.objectId String` | 会被展开为 className 和 objectId 两个字段 |
| GeoPoint | Point | 试验性支持 |
| Number | Float64 |
| Object | String | 以 JSON 字符串的形式存储，需要用相关函数提取其中的字段 | `visitParamExtractInt64(object, 'id')` |
| Pointer | `*.className String` |
| `*.objectId String` | 会被展开为 className 和 objectId 两个字段 |

数据仓库中所支持的类型列表，可参考 [ClickHouse 数据类型](https://clickhouse.com/docs/en/sql-reference/data-types/) 文档。如何在类型之间转换，可参考 [类型转换](https://clickhouse.com/docs/en/sql-reference/functions/type-conversion-functions/) 文档。

## 查询语法

数据仓库仅支持 `select` 查询。语法结构大致如下，

    SELECT column1, column2, expr ...
| FROMtable | (subquery) |
| [INNER | LEFT | RIGHT | FULL | CROSS]JOIN(subquery) | table(ON<expr_list>) |
    [WHERE expr]
    [GROUPBY expr_list]
    [HAVING expr]
    [ORDERBY expr_list]
    [LIMIT[skip,]n]
    [UNION...]

注意字符串，日期等值必需用**单引号** 引用；而对于字段或表名中有特殊字符的情况，可使用反引号进行引用。比如

    WHERE order_status ='delivered'
    AND`from`='example.com'

更多查询语法请参考 [ClickHouse 文档指南](https://clickhouse.com/docs/en/sql-reference/statements/select/)。

## 常见用例推荐

#### 使用 visitParamExtract* 提取 json 字段

在数据同步的过程中，多层嵌套的 object 对象会以 json 字符串的形式入库。为了提取 json 字符串中的字段，推荐使用 `visitParamExtract*` 来提取字段，比如

    SELECT visitParamExtractString('{"abc":"\\u263a"}','abc')='☺';

在嵌套复杂，且出现有重名字段时，可使用 `JSONExtract*`，比如

    SELECT JSONExtractFloat('{"a": "hello", "b": [-100, 200.0, 300]}','b',2)=200.0

更多的 JSON 提取函数可参考[官方文档](https://clickhouse.com/docs/en/sql-reference/functions/json-functions/#visitparamextractuintparams-name)。

#### 使用 toTimeZone 进行时区转换

日期的展示默认以服务端时区展示，国内节点为东八区时间 (Asia/Shanghai)。如果不符合预期，可以使用 `toTimeZone` 将日期转换到特定的时区展示。

    toTimeZone(createdAt,'Asia/Shanghai')

#### 使用 toYYYYMMDD 进行按日期统计

在按照日期进行统计分析时，可以使用 `toYYYYMMDD` 将日期字符串化后进行 group by 统计。同时需要注意时区的处理，比如，

    GROUPBY toYYYYMMDD(toTimeZone(createdAt,'Asia/Shanghai'))

#### 使用 argMax 提取「最新版本」数据

在遇到重复数据时，可以使用 argMax 来提取最后一条数据作为「最新版本」的数据。比如我们可以提取某一个订单的最新状态，

    SELECT
      orderId,
      argMax(status, updatedAt)ASstatus
    FROM my_class
    GROUPBY orderId

## 其他限制

* 基于安全原因，`_User` 表的 `sessionToken`、`password`、`salt`、`authData` 字段，以及所有表的 `ACL` 字段都不支持同步。
* 基于性能考量，`_Conversation` 表的 `m` 和 `mu` 这样的大数组字段暂不支持同步。
* 为了更好的隔离应用之间的影响，我们会对来自同一个应用的慢查询进行配额限制。比如，我们仅允许最多不超过 3 个慢查询同时进行。如果一个查询耗时超过 5 秒，则为慢查询。

## REST API

敬请期待。

## 计费

数据仓库功能仅对商用版应用开放，且目前处于 Beta 预览阶段，暂不收费。进入正式阶段，我们将对「存储空间」和「计算资源」两个维度进行计费。
