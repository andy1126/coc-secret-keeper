from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str = Field(description="角色姓名")
    background: str = Field(description="角色背景")
    personality: str = Field(description="角色性格")
    motivation: str = Field(description="核心动机")
    arc: str = Field(description="角色弧线")
    relationships: list[str] = Field(default_factory=list, description="人物关系")


class Entity(BaseModel):
    name: str = Field(description="神话实体名称")
    description: str = Field(description="实体描述")
    influence: str = Field(description="对人类的影响方式")


class WorldSetting(BaseModel):
    era: str = Field(description="故事时代背景")
    locations: list[str] = Field(default_factory=list, description="故事地点")
    entities: list[Entity] = Field(default_factory=list, description="神话实体")
    forbidden_knowledge: str = Field(default="", description="禁忌知识")
    rules: list[str] = Field(default_factory=list, description="世界观规则")
    characters: list[Character] = Field(default_factory=list, description="角色列表")


class ChapterOutline(BaseModel):
    number: int = Field(description="章节序号")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    mood: str = Field(description="情绪基调")
    word_target: int = Field(description="目标字数")
    foreshadowing: list[str] = Field(default_factory=list, description="伏笔列表")
    payoffs: list[str] = Field(default_factory=list, description="回收点列表")


class ReviewIssue(BaseModel):
    category: str = Field(
        description="问题类别: wording/grammar/atmosphere/plot/worldview/completeness"
    )
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
