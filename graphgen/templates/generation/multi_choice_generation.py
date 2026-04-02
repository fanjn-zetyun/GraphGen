TEMPLATE_GENERATION_ZH: str = """请根据上下文资料生成独立的知识问答单选题，每个选择题包含四个选项，其中仅有一个正确答案，其他三个为干扰项。

生成要求：
1. **语言一致性**：若上下文资料为中文，则生成中文问题；若为英文，则生成英文问题
2. **数量**：每个上下文资料生成{num_of_questions}个选择题
3. **独立性**：每个问题必须完整独立，不依赖其他问题
4. **准确性**：正确答案必须能从原文直接得出，干扰项需合理且有区分度

输出格式：
QA_PAIR_START
QUESTION_START
问题文本
QUESTION_END
OPTIONS_START
A. 选项A文本
B. 选项B文本
C. 选项C文本
D. 选项D文本
OPTIONS_END
ANSWER_START
正确答案选项字母
ANSWER_END
QA_PAIR_END

示例（根据iPad Air 2生成2题）：
QA_PAIR_START
QUESTION_START
iPad Air 2的发布年份是？
QUESTION_END
OPTIONS_START
A. 2012年
B. 2014年
C. 2015年
D. 2017年
OPTIONS_END
ANSWER_START
B
ANSWER_END
QA_PAIR_END
QA_PAIR_START
QUESTION_START
iPad Air 2搭载的处理器型号是？
QUESTION_END
OPTIONS_START
A. A8
B. A9X
C. A8X
D. A10
OPTIONS_END
ANSWER_START
C
ANSWER_END
QA_PAIR_END


上下文资料：
{context}

请为以下资料生成{num_of_questions}个选择题：
"""

TEMPLATE_GENERATION_EN: str = """Generate independent multiple-choice questions \
based on the provided context. Each question should contain four options \
with only one correct answer and three distractors.

Requirements:
1. **Language Consistency**: Generate in the same language as the context (Chinese/English)
2. **Quantity**: Generate {num_of_questions} questions per context
3. **Independence**: Each question must be self-contained
4. **Accuracy**: Correct answer must be derivable from text, distractors should be plausible

Output Format:
QA_PAIR_START
QUESTION_START
Question text
QUESTION_END
OPTIONS_START
A. Option A text
B. Option B text
C. Option C text
D. Option D text
OPTIONS_END
ANSWER_START
Correct option letter
ANSWER_END
QA_PAIR_END

Example (2 questions):
QA_PAIR_START
QUESTION_START
What year was the iPad Air 2 released?
QUESTION_END
OPTIONS_START
A. 2012
B. 2014
C. 2015
D. 2017
OPTIONS_END
ANSWER_START
B
ANSWER_END
QA_PAIR_END
QA_PAIR_START
QUESTION_START
Which processor does iPad Air 2 use?
QUESTION_END
OPTIONS_START
A. A8
B. A9X
C. A8X
D. A10
OPTIONS_END
ANSWER_START
C
ANSWER_END
QA_PAIR_END

Context:
{context}

Please generate {num_of_questions} questions for the following context:
"""


MCQ_GENERATION_PROMPT = {"zh": TEMPLATE_GENERATION_ZH, "en": TEMPLATE_GENERATION_EN}
