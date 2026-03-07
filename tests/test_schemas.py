from models.schemas import Character, Entity, WorldSetting, ChapterOutline


def test_character_creation():
    char = Character(
        name="张三",
        background="考古学家",
        personality="好奇、固执",
        motivation="寻找失落的真相",
        arc="从怀疑到疯狂",
        relationships=["李四：同事", "王五：导师"],
    )
    assert char.name == "张三"
    assert len(char.relationships) == 2


def test_entity_creation():
    entity = Entity(
        name="古老者",
        description="来自星际的古老生物",
        influence="通过梦境影响人类心智",
    )
    assert entity.name == "古老者"


def test_world_setting_creation():
    world = WorldSetting(
        era="1920年代",
        locations=["阿卡姆镇", "密斯卡托尼克大学"],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="人类并非万物之主",
        rules=["不可直视古神", "知识带来疯狂"],
        characters=[
            Character(
                name="张三",
                background="学者",
                personality="好奇",
                motivation="求知",
                arc="堕落",
                relationships=[],
            )
        ],
    )
    assert len(world.locations) == 2
    assert len(world.characters) == 1


def test_chapter_outline_creation():
    chapter = ChapterOutline(
        number=1,
        title="开端",
        summary="主角发现神秘手稿",
        mood="悬疑、不安",
        word_target=3000,
        foreshadowing=["手稿上的符号", "奇怪的梦境"],
        payoffs=[],
    )
    assert chapter.number == 1
    assert chapter.word_target == 3000
