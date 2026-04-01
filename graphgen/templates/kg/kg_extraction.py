# pylint: disable=C0301
TEMPLATE_EN: str = """You are an NLP expert, skilled at analyzing text to extract named entities and their relationships.

-Goal-
Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.
Use English as output language.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, use same language as input text. If English, capitalized the name.
- entity_type: One of the following types: [{entity_types}]
- entity_summary: Comprehensive summary of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_summary>)

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_summary: explanation as to why you think the source entity and the target entity are related to each other
Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_summary>)

3. Identify high-level key words that summarize the main concepts, themes, or topics of the entire text. These should capture the overarching ideas present in the document.
Format the content-level key words as ("content_keywords"{tuple_delimiter}<high_level_keywords>)

4. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

5. When finished, output {completion_delimiter}

################
-Examples-
################
-Example 1-
Text:
################
In the second century of the Christian Era, the empire of Rome comprehended the fairest part of the earth, and the most civilized portion of mankind. The frontiers of that extensive monarchy were guarded by ancient renown and disciplined valor. The gentle but powerful influence of laws and manners had gradually cemented the union of the provinces. Their peaceful inhabitants enjoyed and abused the advantages of wealth and luxury. The image of a free constitution was preserved with decent reverence: the Roman senate appeared to possess the sovereign authority, and devolved on the emperors all the executive powers of government. During a happy period of more than fourscore years, the public administration was conducted by the virtue and abilities of Nerva, Trajan, Hadrian, and the two Antonines.
################
Output:
("entity"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"organization"{tuple_delimiter}"The dominant empire of the second century CE, encompassing the most developed regions of the known world."){record_delimiter}
("entity"{tuple_delimiter}"Second Century CE"{tuple_delimiter}"date"{tuple_delimiter}"Time period of the Christian Era when the Roman Empire was at its height."){record_delimiter}
("entity"{tuple_delimiter}"Rome"{tuple_delimiter}"location"{tuple_delimiter}"The capital and heart of the Roman Empire."){record_delimiter}
("entity"{tuple_delimiter}"Roman Senate"{tuple_delimiter}"organization"{tuple_delimiter}"Legislative body that appeared to hold sovereign authority in Rome."){record_delimiter}
("entity"{tuple_delimiter}"Nerva"{tuple_delimiter}"person"{tuple_delimiter}"Roman emperor who contributed to the public administration during a prosperous period."){record_delimiter}
("entity"{tuple_delimiter}"Trajan"{tuple_delimiter}"person"{tuple_delimiter}"Roman emperor known for his virtue and administrative abilities."){record_delimiter}
("entity"{tuple_delimiter}"Hadrian"{tuple_delimiter}"person"{tuple_delimiter}"Roman emperor who governed during the empire's peaceful period."){record_delimiter}
("entity"{tuple_delimiter}"Antonines"{tuple_delimiter}"person"{tuple_delimiter}"Two Roman emperors who ruled during a period of prosperity and good governance."){record_delimiter}
("entity"{tuple_delimiter}"Roman Law"{tuple_delimiter}"concept"{tuple_delimiter}"System of laws and manners that unified the provinces of the Roman Empire."){record_delimiter}
("relationship"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"Roman Law"{tuple_delimiter}"The empire was unified and maintained through the influence of its laws and customs."){record_delimiter}
("relationship"{tuple_delimiter}"Roman Senate"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"The Senate appeared to possess sovereign authority while delegating executive powers to emperors."){record_delimiter}
("relationship"{tuple_delimiter}"Nerva"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"Nerva was one of the emperors who contributed to the empire's successful administration."){record_delimiter}
("relationship"{tuple_delimiter}"Trajan"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"Trajan was one of the emperors who governed during the empire's prosperous period."){record_delimiter}
("relationship"{tuple_delimiter}"Hadrian"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"Hadrian was one of the emperors who managed the empire's administration effectively."){record_delimiter}
("relationship"{tuple_delimiter}"Antonines"{tuple_delimiter}"Roman Empire"{tuple_delimiter}"The Antonines were emperors who helped maintain the empire's prosperity through their governance."){record_delimiter}
("content_keywords"{tuple_delimiter}"Roman governance, imperial prosperity, law and order, civilized society"){completion_delimiter}

-Example 2-
Text:
#############
Overall, the analysis of the OsDT11 sequence demonstrated that this protein belongs to the CRP family. Since OsDT11 is predicted to be a secreted protein, the subcellular localization of OsDT11 was determined by fusing the OsDT11 ORF to RFP in a p35S::RFP vector by in vivo protein targeting in NB epidermal cells by performing an Agrobacterium tumefaciens-mediated transient assay. After incubation for 48 h, the RFP signals were mainly detected in the cell-wall of OsDT11-RFP transformed cells, while the control cells (transformed with the RFP construct) displayed ubiquitous RFP signals, demonstrating that OsDT11 is a secreted signal peptide. Moreover, when the infiltrated leaf sections were plasmolyzed, the OsDT11-RFP fusion proteins were located on the cell wall.
#############
Output:
("entity"{tuple_delimiter}"OsDT11"{tuple_delimiter}"gene"{tuple_delimiter}"A protein sequence belonging to the CRP family, demonstrated to be a secreted signal peptide that localizes to cell walls."){record_delimiter}
("entity"{tuple_delimiter}"CRP family"{tuple_delimiter}"science"{tuple_delimiter}"A protein family to which OsDT11 belongs, characterized by specific structural and functional properties."){record_delimiter}
("entity"{tuple_delimiter}"RFP"{tuple_delimiter}"technology"{tuple_delimiter}"Red Fluorescent Protein, used as a fusion marker to track protein localization in cells."){record_delimiter}
("entity"{tuple_delimiter}"p35S::RFP vector"{tuple_delimiter}"technology"{tuple_delimiter}"A genetic construct used for protein expression and visualization studies, containing the 35S promoter and RFP marker."){record_delimiter}
("entity"{tuple_delimiter}"NB epidermal cells"{tuple_delimiter}"nature"{tuple_delimiter}"Plant epidermal cells used as the experimental system for protein localization studies."){record_delimiter}
("entity"{tuple_delimiter}"Agrobacterium tumefaciens"{tuple_delimiter}"nature"{tuple_delimiter}"A bacteria species used for transferring genetic material into plant cells in laboratory experiments."){record_delimiter}
("relationship"{tuple_delimiter}"OsDT11"{tuple_delimiter}"CRP family"{tuple_delimiter}"OsDT11 is identified as a member of the CRP family through sequence analysis."){record_delimiter}
("relationship"{tuple_delimiter}"OsDT11"{tuple_delimiter}"RFP"{tuple_delimiter}"OsDT11 was fused to RFP to study its cellular localization."){record_delimiter}
("relationship"{tuple_delimiter}"Agrobacterium tumefaciens"{tuple_delimiter}"NB epidermal cells"{tuple_delimiter}"Agrobacterium tumefaciens was used to transfer genetic material into NB epidermal cells through a transient assay."){record_delimiter}
("relationship"{tuple_delimiter}"OsDT11"{tuple_delimiter}"NB epidermal cells"{tuple_delimiter}"OsDT11's subcellular localization was studied in NB epidermal cells, showing cell wall targeting."){record_delimiter}
("content_keywords"{tuple_delimiter}"protein localization, gene expression, cellular biology, molecular techniques"){completion_delimiter}

################
-Real Data-
################
Entity_types: {entity_types}
Text: {input_text}
################
Output:
"""


TEMPLATE_ZH: str = """你是一个NLP专家，擅长分析文本提取命名实体和关系。

-目标-
给定一个实体类型列表和可能与列表相关的文本，从文本中识别所有这些类型的实体，以及这些实体之间所有的关系。
使用中文作为输出语言。

-步骤-
1. 识别所有实体。对于每个识别的实体，提取以下信息：
   - entity_name：实体的名称，首字母大写
   - entity_type：以下类型之一：[{entity_types}]
   - entity_summary：实体的属性与活动的全面总结
   将每个实体格式化为("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_summary>)
   
2. 从步骤1中识别的实体中，识别所有（源实体，目标实体）对，这些实体彼此之间*明显相关*。
   对于每对相关的实体，提取以下信息：
   - source_entity：步骤1中识别的源实体名称
   - target_entity：步骤1中识别的目标实体名称
   - relationship_summary：解释为什么你认为源实体和目标实体彼此相关
   将每个关系格式化为("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_summary>)

3. 识别总结整个文本的主要概念、主题或话题的高级关键词。这些应该捕捉文档中存在的总体思想。
   将内容级关键词格式化为("content_keywords"{tuple_delimiter}<high_level_keywords>)

4. 以中文返回步骤1和2中识别出的所有实体和关系的输出列表。使用**{record_delimiter}**作为列表分隔符。

5. 完成后，输出{completion_delimiter}

################
-示例-
################
-示例 1-
文本：
################
人工智能是计算机科学的一个重要分支，旨在研究和开发能够模拟、延伸和扩展人类智能的理论、方法、技术及应用系统。机器学习是人工智能的核心技术之一，它使计算机系统能够从数据中自动学习并改进，而无需进行明确的编程。深度学习是机器学习的一个重要子领域，通过构建多层神经网络来模拟人脑的学习过程。自然语言处理是人工智能的另一个重要分支，致力于实现人与计算机之间用自然语言进行有效通信。图像识别技术则利用深度学习算法，使计算机能够识别和处理图像中的物体、场景和文字。
################
输出：
("entity"{tuple_delimiter}"人工智能"{tuple_delimiter}"concept"{tuple_delimiter}"人工智能是计算机科学的一个重要分支，旨在研究和开发能够模拟、延伸和扩展人类智能的理论、方法、技术及应用系统。"){record_delimiter}
("entity"{tuple_delimiter}"机器学习"{tuple_delimiter}"technology"{tuple_delimiter}"机器学习是人工智能的核心技术之一，它使计算机系统能够从数据中自动学习并改进，而无需进行明确的编程。"){record_delimiter}
("entity"{tuple_delimiter}"深度学习"{tuple_delimiter}"technology"{tuple_delimiter}"深度学习是机器学习的一个重要子领域，通过构建多层神经网络来模拟人脑的学习过程。"){record_delimiter}
("entity"{tuple_delimiter}"自然语言处理"{tuple_delimiter}"technology"{tuple_delimiter}"自然语言处理是人工智能的另一个重要分支，致力于实现人与计算机之间用自然语言进行有效通信。"){record_delimiter}
("entity"{tuple_delimiter}"图像识别"{tuple_delimiter}"technology"{tuple_delimiter}"图像识别技术利用深度学习算法，使计算机能够识别和处理图像中的物体、场景和文字。"){record_delimiter}
("entity"{tuple_delimiter}"神经网络"{tuple_delimiter}"concept"{tuple_delimiter}"神经网络是深度学习的核心组件，用于模拟人脑的学习过程。"){record_delimiter}
("entity"{tuple_delimiter}"计算机科学"{tuple_delimiter}"science"{tuple_delimiter}"计算机科学是人工智能所属的学科领域。"){record_delimiter}
("relationship"{tuple_delimiter}"人工智能"{tuple_delimiter}"计算机科学"{tuple_delimiter}"人工智能是计算机科学的一个重要分支。"){record_delimiter}
("relationship"{tuple_delimiter}"机器学习"{tuple_delimiter}"人工智能"{tuple_delimiter}"机器学习是人工智能的核心技术之一。"){record_delimiter}
("relationship"{tuple_delimiter}"深度学习"{tuple_delimiter}"机器学习"{tuple_delimiter}"深度学习是机器学习的一个重要子领域。"){record_delimiter}
("relationship"{tuple_delimiter}"自然语言处理"{tuple_delimiter}"人工智能"{tuple_delimiter}"自然语言处理是人工智能的另一个重要分支。"){record_delimiter}
("relationship"{tuple_delimiter}"图像识别"{tuple_delimiter}"深度学习"{tuple_delimiter}"图像识别技术利用深度学习算法实现。"){record_delimiter}
("relationship"{tuple_delimiter}"深度学习"{tuple_delimiter}"神经网络"{tuple_delimiter}"深度学习通过构建多层神经网络来模拟人脑的学习过程。"){record_delimiter}
("content_keywords"{tuple_delimiter}"人工智能, 机器学习, 深度学习, 自然语言处理, 神经网络, 图像识别"){completion_delimiter}

-示例 2-
文本：
################
北京是中华人民共和国的首都，位于华北平原的北部，背靠燕山山脉，是一座拥有三千多年历史的古都。北京不仅是中国的政治中心，也是重要的文化教育中心。北京大学和清华大学是中国最顶尖的两所高等学府，均位于北京市海淀区。故宫博物院位于北京市中心，是明清两代的皇家宫殿，也是世界上现存规模最大、保存最为完整的木质结构古建筑群。
################
输出：
("entity"{tuple_delimiter}"北京"{tuple_delimiter}"location"{tuple_delimiter}"北京是中华人民共和国的首都，位于华北平原的北部，背靠燕山山脉，是一座拥有三千多年历史的古都。"){record_delimiter}
("entity"{tuple_delimiter}"中华人民共和国"{tuple_delimiter}"organization"{tuple_delimiter}"中华人民共和国是位于东亚的社会主义国家，北京是其首都。"){record_delimiter}
("entity"{tuple_delimiter}"华北平原"{tuple_delimiter}"location"{tuple_delimiter}"华北平原是中国第二大平原，位于中国北部，北京市位于其北端。"){record_delimiter}
("entity"{tuple_delimiter}"燕山山脉"{tuple_delimiter}"location"{tuple_delimiter}"燕山山脉位于华北平原北部，北京市背靠此山脉。"){record_delimiter}
("entity"{tuple_delimiter}"北京大学"{tuple_delimiter}"organization"{tuple_delimiter}"北京大学是中国最顶尖的高等学府之一，位于北京市海淀区。"){record_delimiter}
("entity"{tuple_delimiter}"清华大学"{tuple_delimiter}"organization"{tuple_delimiter}"清华大学是中国最顶尖的高等学府之一，位于北京市海淀区。"){record_delimiter}
("entity"{tuple_delimiter}"海淀区"{tuple_delimiter}"location"{tuple_delimiter}"海淀区是北京市的一个市辖区，北京大学和清华大学均位于此地。"){record_delimiter}
("entity"{tuple_delimiter}"故宫博物院"{tuple_delimiter}"location"{tuple_delimiter}"故宫博物院位于北京市中心，是明清两代的皇家宫殿，是世界上现存规模最大、保存最为完整的木质结构古建筑群。"){record_delimiter}
("relationship"{tuple_delimiter}"北京"{tuple_delimiter}"中华人民共和国"{tuple_delimiter}"北京是中华人民共和国的首都。"){record_delimiter}
("relationship"{tuple_delimiter}"北京"{tuple_delimiter}"华北平原"{tuple_delimiter}"北京位于华北平原的北部。"){record_delimiter}
("relationship"{tuple_delimiter}"北京"{tuple_delimiter}"燕山山脉"{tuple_delimiter}"北京背靠燕山山脉。"){record_delimiter}
("relationship"{tuple_delimiter}"北京大学"{tuple_delimiter}"海淀区"{tuple_delimiter}"北京大学位于北京市海淀区。"){record_delimiter}
("relationship"{tuple_delimiter}"清华大学"{tuple_delimiter}"海淀区"{tuple_delimiter}"清华大学位于北京市海淀区。"){record_delimiter}
("relationship"{tuple_delimiter}"故宫博物院"{tuple_delimiter}"北京"{tuple_delimiter}"故宫博物院位于北京市中心。"){record_delimiter}
("content_keywords"{tuple_delimiter}"北京, 首都, 高等教育, 故宫, 海淀区, 华北平原"){completion_delimiter}

-真实数据-
实体类型：{entity_types}
文本：{input_text}
################
输出：
"""

CONTINUE_EN: str = """MANY entities and relationships were missed in the last extraction.  \
Add them below using the same format:
"""

CONTINUE_ZH: str = """很多实体和关系在上一次的提取中可能被遗漏了。请在下面使用相同的格式添加它们："""

IF_LOOP_EN: str = """It appears some entities and relationships may have still been missed.  \
Answer YES | NO if there are still entities and relationships that need to be added.
"""

IF_LOOP_ZH: str = """看起来可能仍然遗漏了一些实体和关系。如果仍有实体和关系需要添加，请回答YES | NO。"""

KG_EXTRACTION_PROMPT: dict = {
    "en": {
        "TEMPLATE": TEMPLATE_EN,
        "CONTINUE": CONTINUE_EN,
        "IF_LOOP": IF_LOOP_EN,
    },
    "zh": {
        "TEMPLATE": TEMPLATE_ZH,
        "CONTINUE": CONTINUE_ZH,
        "IF_LOOP": IF_LOOP_ZH,
    },
    "FORMAT": {
        "tuple_delimiter": "|||",
        "record_delimiter": "##",
        "completion_delimiter": "<|COMPLETE|>",
        "entity_types": "concept, date, location, keyword, organization, person, event, work, nature, artificial, \
science, technology, mission, gene",
    },
}
