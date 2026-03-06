# 页面内容

管理应用页面内容的数据。

## app_pages

应用页面表，按 `page_key + client_type + locale` 存储当前有效正文。

```txt
id -- Snowflake ID
page_key -- 页面标识
client_type -- 客户端标识
locale -- 语言
page_category -- 页面分类：1=policy，2=info
title -- 页面标题
source_type -- 真相源类型：1=markdown，2=html
content_md -- Markdown 内容
content_html -- HTML 内容
status -- 页面状态
created_at
updated_at
```
