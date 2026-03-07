from pydantic import BaseModel, Field
from models.schemas import WorldSetting, ChapterOutline


class StoryContext(BaseModel):
    seed: dict = Field(default_factory=dict, description="故事种子/初始想法")
    world: WorldSetting | None = Field(default=None, description="世界观设定")
    outline: list[ChapterOutline] = Field(default_factory=list, description="章节大纲")
    chapters: list[str] = Field(default_factory=list, description="已生成章节正文")
    review_notes: list[str] = Field(default_factory=list, description="审核记录")
    current_stage: str = Field(default="brainstorm", description="当前阶段")

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "StoryContext":
        return cls.model_validate(data)
