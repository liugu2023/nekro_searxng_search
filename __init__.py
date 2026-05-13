"""
# SearXNG 搜索工具 (SearXNG Search)

为 AI 提供基于自建 SearXNG 实例的联网搜索能力，用于查询实时网页信息。

## 主要功能

- **自建实例搜索**: 通过你自己的 SearXNG 实例完成联网搜索，避免依赖第三方商业搜索 API。
- **多维筛选**: 支持分类、指定引擎、时间范围和页码等常见检索参数。
- **结果整合**: 将搜索结果、直接答案和建议统一整理后返回给 AI，用于后续综合分析。

## 使用方法

此插件主要由 AI 在后台自动调用。当 AI 需要实时事实、新闻、网站信息或外部资料时，可以调用本插件发起搜索。

## 配置说明

- **SearXNG 实例地址**: 你的 SearXNG 基础地址，插件会自动拼接 `/search`。
- **默认分类**: 未显式指定分类时使用的搜索分类，通常为 `general`。
- **默认搜索语言**: 可留空让实例自行决定，也可固定为 `zh-CN`、`en-US` 等语言。
- **启用系统代理**: 如你的 SearXNG 实例需要通过系统代理访问，可开启此选项。

注意：目标 SearXNG 实例必须启用 `json` 输出格式，否则插件无法正常解析结果。
"""

import time
from typing import Any, Literal, Optional

from httpx import AsyncClient, HTTPError, HTTPStatusError, Timeout
from pydantic import BaseModel, Field, ValidationError

from nekro_agent.api import core, i18n
from nekro_agent.api.plugin import (
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)
from nekro_agent.api.schemas import AgentCtx

plugin = NekroPlugin(
    name="SearXNG搜索工具",
    module_name="nekro_searxng_search",
    description="通过自建 SearXNG 实例提供联网搜索能力",
    version="0.1.0",
    author="liugu",
    url="https://github.com/KroMiose/nekro-agent",
    i18n_name=i18n.i18n_text(
        zh_CN="SearXNG搜索工具",
        en_US="SearXNG Search Tool",
    ),
    i18n_description=i18n.i18n_text(
        zh_CN="通过自建 SearXNG 实例提供联网搜索能力",
        en_US="Provides web search through a self-hosted SearXNG instance",
    ),
    allow_sleep=True,
    sleep_brief="用于联网搜索实时信息与外部事实。只有在知识不足或需要最新信息时再激活。",
)


@plugin.mount_config()
class SearXNGSearchConfig(ConfigBase):
    """SearXNG 搜索插件配置"""

    BASE_URL: str = Field(
        default="http://127.0.0.1:8080",
        title="SearXNG 实例地址",
        description="SearXNG 实例基础地址，插件会自动拼接 /search",
        json_schema_extra=ExtraField(
            required=True,
            placeholder="例: https://searx.example.com",
            i18n_title=i18n.i18n_text(
                zh_CN="SearXNG 实例地址",
                en_US="SearXNG Base URL",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="SearXNG 实例基础地址，插件会自动拼接 /search",
                en_US="Base URL of the SearXNG instance; /search will be appended automatically",
            ),
        ).model_dump(),
    )
    DEFAULT_CATEGORY: str = Field(
        default="general",
        title="默认搜索分类",
        description="未指定分类时使用，例如 general、news",
        json_schema_extra=ExtraField(
            placeholder="general",
            i18n_title=i18n.i18n_text(
                zh_CN="默认搜索分类",
                en_US="Default Search Category",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="未指定分类时使用，例如 general、news",
                en_US="Fallback category used when no category is specified, such as general or news",
            ),
        ).model_dump(),
    )
    DEFAULT_LANGUAGE: str = Field(
        default="",
        title="默认搜索语言",
        description="可留空让实例自行决定，例如 zh-CN、en-US",
        json_schema_extra=ExtraField(
            placeholder="例: zh-CN",
            i18n_title=i18n.i18n_text(
                zh_CN="默认搜索语言",
                en_US="Default Search Language",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="可留空让实例自行决定，例如 zh-CN、en-US",
                en_US="Leave empty to let the instance decide, or set values like zh-CN or en-US",
            ),
        ).model_dump(),
    )
    MAX_RESULTS: int = Field(
        default=5,
        ge=1,
        le=10,
        title="最大结果数",
        description="每次返回给 AI 的搜索结果数量",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最大结果数",
                en_US="Maximum Results",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="每次返回给 AI 的搜索结果数量",
                en_US="Maximum number of search results returned to the AI",
            ),
        ).model_dump(),
    )
    THROTTLE_TIME: int = Field(
        default=10,
        ge=0,
        title="搜索冷却时间（秒）",
        description="同一聊天内同一查询在此时间内重复搜索将被阻止",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="搜索冷却时间（秒）",
                en_US="Search Cooldown (seconds)",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="同一聊天内同一查询在此时间内重复搜索将被阻止",
                en_US="Repeated identical searches within the same chat will be blocked during this interval",
            ),
        ).model_dump(),
    )
    TIMEOUT: int = Field(
        default=30,
        ge=1,
        title="请求超时时间（秒）",
        description="搜索请求的最大等待时间",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="请求超时时间（秒）",
                en_US="Request Timeout (seconds)",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="搜索请求的最大等待时间",
                en_US="Maximum wait time for a search request",
            ),
        ).model_dump(),
    )
    VERIFY_SSL: bool = Field(
        default=True,
        title="校验 HTTPS 证书",
        description="关闭后允许连接自签名证书的 HTTPS 实例",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="校验 HTTPS 证书",
                en_US="Verify HTTPS Certificate",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="关闭后允许连接自签名证书的 HTTPS 实例",
                en_US="Disable to allow connections to HTTPS instances with self-signed certificates",
            ),
        ).model_dump(),
    )
    USE_SYSTEM_PROXY: bool = Field(
        default=False,
        title="使用系统代理",
        description="开启后使用系统级默认代理访问 SearXNG 实例",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="使用系统代理",
                en_US="Use System Proxy",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="开启后使用系统级默认代理访问 SearXNG 实例",
                en_US="Use the system default proxy when accessing the SearXNG instance",
            ),
        ).model_dump(),
    )


class SearXNGResult(BaseModel):
    """SearXNG 单条搜索结果"""

    title: str = ""
    url: str = ""
    content: str = ""
    engines: list[str] = Field(default_factory=list)
    publishedDate: Optional[str] = None
    author: Optional[str] = None
    score: Optional[float] = None
    category: Optional[str] = None


class SearXNGResponse(BaseModel):
    """SearXNG 搜索响应"""

    query: str = ""
    number_of_results: Optional[int] = None
    results: list[SearXNGResult] = Field(default_factory=list)
    answers: list[Any] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)


config: SearXNGSearchConfig = plugin.get_config(SearXNGSearchConfig)

_recent_searches: dict[str, float] = {}


def _build_search_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("未配置有效的 SearXNG 实例地址")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("SearXNG 实例地址必须包含 http:// 或 https:// 协议头")
    if normalized.endswith("/search"):
        return normalized
    return f"{normalized}/search"


def _normalize_csv_arg(value: str) -> str:
    return ",".join(part.strip() for part in value.split(",") if part.strip())


def _truncate_text(text: str, max_length: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def _prune_recent_searches() -> None:
    if config.THROTTLE_TIME <= 0:
        _recent_searches.clear()
        return

    expire_before = time.time() - config.THROTTLE_TIME
    expired_keys = [key for key, ts in _recent_searches.items() if ts < expire_before]
    for key in expired_keys:
        _recent_searches.pop(key, None)


def _guard_duplicate_search(cache_key: str) -> None:
    if config.THROTTLE_TIME <= 0:
        return

    _prune_recent_searches()
    last_call_time = _recent_searches.get(cache_key)
    if last_call_time is None:
        return

    remain_seconds = config.THROTTLE_TIME - int(time.time() - last_call_time)
    raise RuntimeError(f"禁止在短时间内重复搜索相同内容，请等待约 {max(remain_seconds, 1)} 秒后重试")


def _remember_search(cache_key: str) -> None:
    if config.THROTTLE_TIME > 0:
        _recent_searches[cache_key] = time.time()


def _format_answer(answer: Any) -> str:
    if isinstance(answer, str):
        return _truncate_text(answer, max_length=180)

    if isinstance(answer, dict):
        ordered_keys = ("answer", "content", "text", "title", "url")
        parts = [_truncate_text(str(answer[key]), max_length=120) for key in ordered_keys if answer.get(key)]
        if parts:
            return " | ".join(parts)

    return _truncate_text(str(answer), max_length=180)


def _format_result_item(index: int, item: SearXNGResult) -> str:
    lines = [f"{index}. {_truncate_text(item.title or item.url or '无标题结果', max_length=120)}"]

    if item.url:
        lines.append(f"   链接: {item.url}")
    if item.content:
        lines.append(f"   摘要: {_truncate_text(item.content)}")
    if item.engines:
        lines.append(f"   来源引擎: {', '.join(item.engines)}")

    meta_parts: list[str] = []
    if item.category:
        meta_parts.append(f"分类: {item.category}")
    if item.publishedDate:
        meta_parts.append(f"发布时间: {item.publishedDate}")
    if item.author:
        meta_parts.append(f"作者: {_truncate_text(item.author, max_length=60)}")
    if item.score is not None:
        meta_parts.append(f"相关度: {item.score:.3f}")

    if meta_parts:
        lines.append(f"   元信息: {' | '.join(meta_parts)}")

    return "\n".join(lines)


def _format_search_response(
    *,
    query: str,
    response: SearXNGResponse,
    categories: str,
    engines: str,
    time_range: Optional[str],
    page: int,
) -> str:
    lines = [
        "[SearXNG Search Results]",
        f"查询: {response.query or query}",
    ]

    scope_parts: list[str] = []
    if categories:
        scope_parts.append(f"分类: {categories}")
    if engines:
        scope_parts.append(f"引擎: {engines}")
    if time_range:
        scope_parts.append(f"时间范围: {time_range}")
    if page > 1:
        scope_parts.append(f"页码: {page}")
    if response.number_of_results is not None:
        scope_parts.append(f"总匹配数: {response.number_of_results}")

    if scope_parts:
        lines.append(f"检索范围: {' | '.join(scope_parts)}")

    answer_lines: list[str] = []
    for answer in response.answers:
        formatted = _format_answer(answer)
        if formatted:
            answer_lines.append(formatted)
    if answer_lines:
        lines.append("直接答案:")
        lines.extend(f"- {answer}" for answer in answer_lines[:3])

    suggestion_candidates = [item.strip() for item in [*response.suggestions, *response.corrections] if item.strip()]
    seen_suggestions: set[str] = set()
    suggestions: list[str] = []
    for item in suggestion_candidates:
        if item in seen_suggestions:
            continue
        seen_suggestions.add(item)
        suggestions.append(item)
    if suggestions:
        lines.append("相关建议:")
        lines.extend(f"- {_truncate_text(item, max_length=120)}" for item in suggestions[:5])

    if response.results:
        lines.append("网页结果:")
        for index, item in enumerate(response.results[: config.MAX_RESULTS], start=1):
            lines.append(_format_result_item(index, item))
    else:
        lines.append("网页结果: 未找到可用结果。")

    lines.append("请综合以上结果回答用户，优先提炼事实并交叉印证，不要逐条照抄搜索摘要。")
    return "\n".join(lines)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="SearXNG搜索",
    description="使用自建 SearXNG 实例搜索实时网页信息",
)
async def searxng_search(
    _ctx: AgentCtx,
    keyword: str,
    categories: str = "",
    engines: str = "",
    time_range: Optional[Literal["day", "month", "year"]] = None,
    page: int = 1,
) -> str:
    """使用 SearXNG 搜索实时网页信息

    Args:
        keyword (str): 搜索关键词或问题
        categories (str): 逗号分隔的分类列表，留空时使用插件默认分类
        engines (str): 逗号分隔的搜索引擎列表，留空时由实例自动选择
        time_range (Optional[str]): 时间范围筛选，可选 day、month、year
        page (int): 结果页码，从 1 开始
    """
    query = keyword.strip()
    if not query:
        raise ValueError("搜索关键词不能为空")
    if page < 1:
        raise ValueError("结果页码必须从 1 开始")

    search_url = _build_search_url(config.BASE_URL)
    resolved_categories = _normalize_csv_arg(categories or config.DEFAULT_CATEGORY)
    resolved_engines = _normalize_csv_arg(engines)
    cache_key = f"{_ctx.chat_key}|{query}|{resolved_categories}|{resolved_engines}|{time_range or ''}|{page}"
    _guard_duplicate_search(cache_key)

    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "pageno": page,
    }
    if resolved_categories:
        params["categories"] = resolved_categories
    if resolved_engines:
        params["engines"] = resolved_engines
    if config.DEFAULT_LANGUAGE.strip():
        params["language"] = config.DEFAULT_LANGUAGE.strip()
    if time_range:
        params["time_range"] = time_range

    headers = {
        "Accept": "application/json",
        "User-Agent": "Nekro-Agent SearXNG Search Plugin/0.1.0",
    }
    proxy = core.config.DEFAULT_PROXY.strip() if config.USE_SYSTEM_PROXY and core.config.DEFAULT_PROXY.strip() else None
    timeout = Timeout(timeout=float(config.TIMEOUT), connect=min(float(config.TIMEOUT), 10.0))

    try:
        async with AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            proxy=proxy,
            verify=config.VERIFY_SSL,
        ) as client:
            response = await client.get(search_url, params=params, headers=headers)
            response.raise_for_status()
    except HTTPStatusError as exc:
        plugin.logger.exception("SearXNG 搜索请求返回异常状态码")
        if exc.response.status_code in {403, 404, 406}:
            raise RuntimeError(
                "SearXNG 实例拒绝了 JSON 搜索请求，请确认实例已启用 json 输出格式并允许访问 /search"
            ) from exc
        raise RuntimeError(f"SearXNG 搜索请求失败，状态码: {exc.response.status_code}") from exc
    except HTTPError as exc:
        plugin.logger.exception("SearXNG 搜索请求失败")
        raise RuntimeError(f"SearXNG 搜索请求失败: {exc!s}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        plugin.logger.exception("SearXNG 搜索响应不是合法 JSON")
        raise RuntimeError(
            "SearXNG 实例未返回合法 JSON，请确认实例已启用 json 输出格式，且反向代理未改写响应"
        ) from exc

    try:
        parsed = SearXNGResponse.model_validate(payload)
    except ValidationError as exc:
        plugin.logger.exception("SearXNG 搜索响应结构不符合预期")
        raise RuntimeError(f"SearXNG 返回的 JSON 结构不符合预期: {exc!s}") from exc

    _remember_search(cache_key)
    return _format_search_response(
        query=query,
        response=parsed,
        categories=resolved_categories,
        engines=resolved_engines,
        time_range=time_range,
        page=page,
    )


@plugin.mount_cleanup_method()
async def clean_up() -> None:
    """清理插件缓存状态"""
    _recent_searches.clear()
