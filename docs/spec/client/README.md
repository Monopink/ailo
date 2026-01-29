# 客户端规范

本目录为客户端相关规范的统一入口，原 `docs/spec/app/` 与 `docs/spec/mini-program/` 内容已迁移至此。

## 目录结构

- `base/`：跨端通用规范
- `app/`：App 端规范与原型
- `mini-program/`：小程序端规范与原型

## 快速入口

- [通用规范索引](base/README.md)
- [App 端规范](app/README.md)
- [小程序端规范](mini-program/README.md)

## 使用说明

- 通用规则优先写入 `base/`
- 端特有差异写入各自目录，并引用 `base/`
