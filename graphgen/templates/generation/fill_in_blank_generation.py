TEMPLATE_ZH = """请根据上下文资料生成独立的知识问答填空题。填空题的答案必须能在原文中直接找到。

生成要求：
1. **语言一致性**：若上下文资料为中文，则生成中文问题；若为英文，则生成英文问题
2. **数量**：每个上下文资料生成{num_of_questions}个填空题
3. **独立性**：每个问题必须完整独立，不依赖其他问题
4. **准确性**：正确答案必须能从原文直接得出
5. **占位符格式**：使用________（四个下划线）作为填空占位符

输出格式：
<qa_pairs>
QA_PAIR_START
QUESTION_START
问题文本（使用________作为占位符）
QUESTION_END
ANSWER_START
正确答案文本（多个空用逗号分隔）
ANSWER_END
QA_PAIR_END
</qa_pairs>

示例（根据iPad Air 2生成2题）：
<qa_pairs>
QA_PAIR_START
QUESTION_START
iPad Air 2 是由________制造的？
QUESTION_END
ANSWER_START
美国苹果公司（Apple）
ANSWER_END
QA_PAIR_END
QA_PAIR_START
QUESTION_START
iPad Air 2 的发布日期是________，上市日期是________。
QUESTION_END
ANSWER_START
2014年10月16日，2014年10月22日
ANSWER_END
QA_PAIR_END
</qa_pairs>


上下文资料：
{context}

请为以下资料生成{num_of_questions}个填空题：
"""


TEMPLATE_EN = """Generate independent fill-in-the-blank questions based on the provided context. \
Answers must be directly derivable from the text.

Requirements:
1. **Language Consistency**: Generate in the same language as the context (Chinese/English)
2. **Quantity**: Generate {num_of_questions} questions per context
3. **Independence**: Each question must be self-contained
4. **Accuracy**: Correct answer must be directly found in the source text
5. **Placeholder Format**: Use ________ (four underscores) as the blank placeholder

Output Format:
<qa_pairs>
QA_PAIR_START
QUESTION_START
Question text (use ________ as placeholder)
QUESTION_END
ANSWER_START
Correct answer text (separate multiple blanks with commas)
ANSWER_END
QA_PAIR_END
</qa_pairs>

Example (2 questions):
<qa_pairs>
QA_PAIR_START
QUESTION_START
The iPad Air 2 was manufactured by ________?
QUESTION_END
ANSWER_START
Apple Inc.
ANSWER_END
QA_PAIR_END
QA_PAIR_START
QUESTION_START
The iPad Air 2 was released on ________ and launched on ________.
QUESTION_END
ANSWER_START
October 16, 2014, October 22, 2014
ANSWER_END
QA_PAIR_END
</qa_pairs>

Context:
{context}

Please generate {num_of_questions} fill-in-the-blank questions for the following context:
"""


FILL_IN_BLANK_GENERATION_PROMPT = {
    "zh": TEMPLATE_ZH,
    "en": TEMPLATE_EN,
}
