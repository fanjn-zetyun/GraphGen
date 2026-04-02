TEMPLATE_ZH = """请根据上下文资料生成独立的知识问答不定项选择题，每个选择题包含四个选项，其中有若干个正确答案（至少一个），其他为干扰项。

生成要求：
1. **语言一致性**：若上下文资料为中文，则生成中文问题；若为英文，则生成英文问题
2. **数量**：每个上下文资料生成{num_of_questions}个选择题
3. **独立性**：每个问题必须完整独立，不依赖其他问题
4. **准确性**：正确答案必须能从原文直接得出，干扰项需合理且有区分度
5. **答案格式**：当有多个正确答案时，用逗号分隔选项字母，如"A, B, C"

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
正确答案选项字母（多个答案用逗号分隔）
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
以下哪些是 iPad Air 2 的特点？
QUESTION_END
OPTIONS_START
A. Touch ID指纹识别功能
B. A8X高效处理器
C. 十百万像素前置相机
D. 八百万像素后置相机镜头
OPTIONS_END
ANSWER_START
A, B, D
ANSWER_END
QA_PAIR_END


上下文资料：
{context}

请为以下资料生成{num_of_questions}个不定项选择题：
"""


TEMPLATE_EN = """Generate independent multiple-select knowledge questions \
based on the provided context. Each question should contain four options \
with one or more correct answers and distractors.

Requirements:
1. **Language Consistency**: Generate in the same language as the context (Chinese/English)
2. **Quantity**: Generate {num_of_questions} questions per context
3. **Independence**: Each question must be self-contained
4. **Accuracy**: Correct answer(s) must be derivable from text, distractors should be plausible
5. **Answer Format**: For multiple correct answers, separate option letters with commas, e.g., "A, B, C"

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
Correct option letter(s) (separate multiple answers with commas)
ANSWER_END
QA_PAIR_END

Example (2 questions):
QA_PAIR_START
QUESTION_START
What are the features of iPad Air 2?
QUESTION_END
OPTIONS_START
A. Touch ID fingerprint recognition
B. A8X processor
C. Ten-megapixel front camera
D. Eight-megapixel rear camera
OPTIONS_END
ANSWER_START
A, B, D
ANSWER_END
QA_PAIR_END
QA_PAIR_START
QUESTION_START
When was iPad Air 2 discontinued?
QUESTION_END
OPTIONS_START
A. March 21, 2016
B. March 21, 2017
C. October 22, 2017
D. October 16, 2016
OPTIONS_END
ANSWER_START
B
ANSWER_END
QA_PAIR_END

Context:
{context}

Please generate {num_of_questions} multiple-select questions for the following context:
"""


MAQ_GENERATION_PROMPT = {"zh": TEMPLATE_ZH, "en": TEMPLATE_EN}
