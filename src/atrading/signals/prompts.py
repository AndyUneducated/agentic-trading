"""版本化 prompt 资产的加载与渲染。

prompt 是受版本控制的资产：变更 → 新版本号 → 触发 prompt 回归评测。加载时校验
`.meta.yaml` 声明的 expected_schema 与代码期望一致，防止"prompt 与解析 schema 漂移"。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_PROMPTS_ROOT = Path(__file__).resolve().parents[3] / "prompts"

_SECTION = re.compile(r"^#\s+(SYSTEM|USER)\s*$")


class PromptTemplate(BaseModel):
    name: str
    version: str
    system: str
    user_template: str
    expected_schema: str

    def render(self, *, symbol: str, as_of: datetime, documents_block: str) -> tuple[str, str]:
        user = (
            self.user_template.replace("{{SYMBOL}}", symbol)
            .replace("{{AS_OF}}", as_of.isoformat())
            .replace("{{DOCUMENTS}}", documents_block)
        )
        return self.system, user


def _split_sections(text: str) -> tuple[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = _SECTION.match(line)
        if match:
            current = match.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    system = "\n".join(sections.get("SYSTEM", [])).strip()
    user = "\n".join(sections.get("USER", [])).strip()
    return system, user


def load_prompt(
    name: str,
    version: str,
    *,
    expected_schema: str,
    root: str | Path = DEFAULT_PROMPTS_ROOT,
) -> PromptTemplate:
    base = Path(root) / name
    body_path = base / f"{version}.md"
    meta_path = base / f"{version}.meta.yaml"
    if not body_path.exists():
        msg = f"prompt 正文缺失: {body_path}"
        raise FileNotFoundError(msg)
    if not meta_path.exists():
        msg = f"prompt 元数据缺失: {meta_path}"
        raise FileNotFoundError(msg)

    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    declared_version = str(meta.get("version"))
    if declared_version != version:
        msg = f"prompt 版本不一致: 文件名 {version} vs meta {declared_version}"
        raise ValueError(msg)
    declared_schema = str(meta.get("expected_schema"))
    if declared_schema != expected_schema:
        msg = f"prompt schema 不匹配: 期望 {expected_schema}，meta 声明 {declared_schema}"
        raise ValueError(msg)

    system, user_template = _split_sections(body_path.read_text(encoding="utf-8"))
    return PromptTemplate(
        name=name,
        version=version,
        system=system,
        user_template=user_template,
        expected_schema=declared_schema,
    )
