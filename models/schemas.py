from typing import Literal

from pydantic import BaseModel, Field, model_validator

THREAD_TYPE = Literal[
    "epistemic",
    "ontological",
    "moral",
    "relational",
    "survival",
    "cosmic",
    "societal",
]

ZONE_TYPE = Literal["setup", "crucible", "aftermath"]


class Character(BaseModel):
    name: str = Field(description="角色姓名")
    background: str = Field(description="角色背景")
    personality: str = Field(description="角色性格")
    motivation: str = Field(description="核心动机")
    arc: str = Field(description="角色弧线")
    relationships: list[str] = Field(default_factory=list, description="人物关系")


class Location(BaseModel):
    name: str = Field(description="地点名称")
    description: str = Field(description="地点描述")


class Entity(BaseModel):
    name: str = Field(description="神话实体名称")
    description: str = Field(description="实体描述")
    influence: str = Field(description="对人类的影响方式")


class Secret(BaseModel):
    content: str = Field(description="秘密内容")
    known_by: list[str] = Field(default_factory=list, description="知情角色")
    layer: int = Field(description="深度层级: 1=表面线索, 2=中层真相, 3=核心真相")


class Tension(BaseModel):
    parties: list[str] = Field(description="涉及角色/势力")
    nature: str = Field(description="冲突性质: 利益/信仰/秘密/生存")
    status: str = Field(description="当前状态: 潜伏/升温/即将爆发")


class TimelineEvent(BaseModel):
    when: str = Field(description="时间描述")
    event: str = Field(description="事件内容")
    consequences: str = Field(description="对当前局面的影响")


class ResearchQuestion(BaseModel):
    topic: str = Field(description="研究主题: genre/psychology/history/dramaturgy")
    question: str = Field(description="具体问题")


class ResearchNote(BaseModel):
    topic: str = Field(description="对应研究主题")
    findings: str = Field(description="研究发现摘要")
    sources: list[str] = Field(default_factory=list, description="参考来源")


class ConflictThread(BaseModel):
    name: str = Field(description="线索名称")
    thread_type: THREAD_TYPE = Field(description="冲突类型")
    description: str = Field(description="描述")
    stakes: str = Field(description="风险")


class DramaticBeat(BaseModel):
    name: str = Field(description="节拍名称（故事专属）")
    description: str = Field(description="具体内容")
    threads: list[str] = Field(description="推进哪些冲突线索")


class StoryZone(BaseModel):
    zone: ZONE_TYPE = Field(description="叙事区域")
    beats: list[DramaticBeat] = Field(description="该区域的节拍")


class ConflictDesign(BaseModel):
    narrative_strategy: str = Field(description="叙事策略")
    threads: list[ConflictThread] = Field(description="冲突线索")
    zones: list[StoryZone] = Field(description="叙事区域")
    tension_shape: str = Field(description="张力曲线描述")
    thematic_throughline: str = Field(description="主题贯穿线")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_format(cls, data):
        """Auto-migrate old 8-beat format to new zone/thread structure."""
        if not isinstance(data, dict):
            return data
        if "inner_conflict" not in data:
            return data

        inner = data.pop("inner_conflict", "")
        outer = data.pop("outer_conflict", "")
        inciting = data.pop("inciting_incident", "")
        midpoint = data.pop("midpoint_reversal", "")
        all_lost = data.pop("all_is_lost", "")
        dark_night = data.pop("dark_night_of_soul", "")
        climax = data.pop("climax", "")
        resolution = data.pop("resolution", "")

        data.setdefault("narrative_strategy", "（从旧格式迁移）")
        data.setdefault("tension_shape", "（从旧格式迁移）")
        data.setdefault("thematic_throughline", "（从旧格式迁移）")
        data.setdefault(
            "threads",
            [
                {
                    "name": "内在冲突",
                    "thread_type": "moral",
                    "description": inner,
                    "stakes": inner,
                },
                {
                    "name": "外在冲突",
                    "thread_type": "survival",
                    "description": outer,
                    "stakes": outer,
                },
            ],
        )
        data.setdefault(
            "zones",
            [
                {
                    "zone": "setup",
                    "beats": [
                        {
                            "name": "激励事件",
                            "description": inciting,
                            "threads": ["内在冲突", "外在冲突"],
                        }
                    ],
                },
                {
                    "zone": "crucible",
                    "beats": [
                        {
                            "name": "中点转折",
                            "description": midpoint,
                            "threads": ["外在冲突"],
                        },
                        {
                            "name": "一无所有时刻",
                            "description": all_lost,
                            "threads": ["内在冲突", "外在冲突"],
                        },
                        {
                            "name": "灵魂暗夜",
                            "description": dark_night,
                            "threads": ["内在冲突"],
                        },
                        {
                            "name": "高潮",
                            "description": climax,
                            "threads": ["内在冲突", "外在冲突"],
                        },
                    ],
                },
                {
                    "zone": "aftermath",
                    "beats": [
                        {
                            "name": "解决/余韵",
                            "description": resolution,
                            "threads": ["内在冲突"],
                        }
                    ],
                },
            ],
        )
        return data

    @model_validator(mode="after")
    def validate_structure(self):
        """Validate structural constraints."""
        if not (2 <= len(self.threads) <= 4):
            raise ValueError(f"threads count must be 2-4, got {len(self.threads)}")
        zone_names = sorted(z.zone for z in self.zones)
        if zone_names != ["aftermath", "crucible", "setup"]:
            raise ValueError(f"zones must be exactly setup/crucible/aftermath, got {zone_names}")
        return self


class NarrativeIssue(BaseModel):
    dimension: str = Field(
        description="审查维度: tension_sufficiency/information_asymmetry/"
        "reversal_space/asset_utilization/character_agency/multi_thread"
    )
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
    target: str = Field(description="修改目标: world/conflict/outline/both")


class WorldSetting(BaseModel):
    era: str = Field(description="故事时代背景")
    locations: list[Location] = Field(default_factory=list, description="故事地点")
    entities: list[Entity] = Field(default_factory=list, description="神话实体")
    forbidden_knowledge: str = Field(default="", description="禁忌知识")
    rules: list[str] = Field(default_factory=list, description="世界观规则")
    characters: list[Character] = Field(default_factory=list, description="角色列表")
    secrets: list[Secret] = Field(default_factory=list, description="世界中的隐藏秘密")
    tensions: list[Tension] = Field(default_factory=list, description="势力/角色间的暗流")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="前史事件")

    @model_validator(mode="before")
    @classmethod
    def normalize_locations(cls, data):
        """Convert string locations to Location objects for backward compatibility."""
        if isinstance(data, dict) and "locations" in data:
            locations = data["locations"]
            if isinstance(locations, list):
                normalized = []
                for loc in locations:
                    if isinstance(loc, str):
                        normalized.append({"name": loc, "description": ""})
                    elif isinstance(loc, dict):
                        normalized.append(loc)
                    elif isinstance(loc, Location):
                        normalized.append(loc)
                data["locations"] = normalized
        return data


class ChapterOutline(BaseModel):
    number: int = Field(description="章节序号")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    mood: str = Field(description="情绪基调")
    word_target: int = Field(description="目标字数")
    foreshadowing: list[str] = Field(default_factory=list, description="伏笔列表")
    payoffs: list[str] = Field(default_factory=list, description="回收点列表")
    pov: str = Field(default="", description="主要叙述视角")
    information_reveal: list[str] = Field(default_factory=list, description="本章揭示的信息")
    twist: str | None = Field(default=None, description="本章反转")
    subplot: str | None = Field(default=None, description="本章推进的副线")
    key_beats: list[str] = Field(default_factory=list, description="关键情节节拍")


class ReviewIssue(BaseModel):
    category: str = Field(
        description="问题类别: wording/grammar/atmosphere/plot/worldview/completeness"
    )
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
