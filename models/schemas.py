from pydantic import BaseModel, Field, model_validator


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


class ConflictDesign(BaseModel):
    inner_conflict: str = Field(description="主角内在冲突")
    outer_conflict: str = Field(description="主要外在冲突")
    inciting_incident: str = Field(description="激励事件")
    midpoint_reversal: str = Field(description="中点转折")
    all_is_lost: str = Field(description="一无所有时刻")
    dark_night_of_soul: str = Field(description="灵魂暗夜")
    climax: str = Field(description="高潮")
    resolution: str = Field(description="解决/余韵")


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


class ReviewIssue(BaseModel):
    category: str = Field(
        description="问题类别: wording/grammar/atmosphere/plot/worldview/completeness"
    )
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
