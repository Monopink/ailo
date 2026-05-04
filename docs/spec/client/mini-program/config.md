## 配置管理

- 运行时配置统一从 `utils/config.ts` 读取
- 资源域名与资源路径统一使用 `ASSET_CONFIG`
- 禁止在页面、组件、`pkg/*` 中硬编码 COS/CDN URL
- 本地覆盖文件使用 `utils/config.local.ts`（不入库），模板文件使用 `utils/config.local.template.ts`（入库）
- 本地覆盖仅允许 `develop` 环境生效,`trial` 与 `release` 环境固定使用默认配置，不读取本地覆盖
- `develop` 环境必须在本地覆盖中提供 `ASSET_CONFIG.cosBaseUrl`，缺失时启动报错
- 本地覆盖白名单: `ASSET_CONFIG`、`API_CONFIG.baseUrl`
