# Nekro SearXNG Search

SearXNG 搜索工具插件，用于通过自建 SearXNG 实例为 Nekro Agent 提供联网搜索能力。

## 功能

- 通过自建 SearXNG 实例搜索实时网页信息
- 支持搜索分类、指定引擎、时间范围和页码
- 自动整理搜索结果、直接答案、建议和修正信息
- 支持搜索冷却，避免短时间重复请求
- 可选择使用系统代理和关闭 HTTPS 证书校验

## 使用

将本目录放入 Nekro Agent 插件工作目录后启用插件：

```text
data/nekro_agent/plugins/workdir/nekro_searxng_search
```

插件模块名为：

```text
nekro_searxng_search
```

## 配置

- `BASE_URL`：SearXNG 实例基础地址
- `DEFAULT_CATEGORY`：默认搜索分类
- `DEFAULT_LANGUAGE`：默认搜索语言
- `MAX_RESULTS`：每次返回给 AI 的最大结果数
- `THROTTLE_TIME`：同一聊天内重复搜索冷却时间
- `TIMEOUT`：请求超时时间
- `VERIFY_SSL`：是否校验 HTTPS 证书
- `USE_SYSTEM_PROXY`：是否使用系统代理

目标 SearXNG 实例需要启用 `json` 输出格式。

## 许可证

MIT
