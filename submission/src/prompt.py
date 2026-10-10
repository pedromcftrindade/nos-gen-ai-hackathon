
prompt = """\
Read this document containing diverse information. Every word is preceded by
a numeric id in square brackets, like [12]word. The ids are not part of the
document; they only identify each word.

This information can be sensitive, personal, private, physical, mental,
political, religious, financial, health related, ethnic, among others. Your
task is to process all this information and abstract all the important or
sensitive topics that the user can choose to censor.

Create a JSON object containing all the sensitive data, organized as follows:
1. The primary keys are the most generic word for the topic (for example:
   Biometric Data, Personal Information, Health Data, Racial Ethnicity).
2. Inside each topic there is another object with more specific sub-topics
   (for example, in Health Data: Health Condition, Mental State, Medication,
   Family History).
3. Inside each sub-topic there is another object where each key is one
   sensitive word and its value is the list of ids where that word occurs.

Rules:
- Capture only the essential words, so the text stays comprehensible when
  those words are replaced with '*'. Never include labels or connecting words.
- Use one key per word. A value with several words gives several keys.
- Write each word exactly as it is in the document, character by character,
  without the id and without punctuation attached to its start or end. Do not
  translate, reformat or correct it.
- Each topic, sub-topic and word appears only once as a key. If a word occurs
  several times, put all its ids in the same list.
- Keep the original language of the document for the words.

Example document:
[0]A [1]paciente [2]Ana [3]Correia, [4]de [5]25 [6]anos [7]e [8]67kg, [9]veio
[10]à [11]consulta [12]por [13]depressão. [14]A [15]mãe [16]de [17]Ana
[18]também [19]tem [20]depressão.

Example output:
{"Personal Information": {"Name": {"Ana": [2, 17], "Correia": [3]},
                          "Age": {"25": [5]}},
 "Biometric Data": {"Weight": {"67kg": [8]}},
 "Health Data": {"Mental State": {"depressão": [13]},
                 "Family History": {"depressão": [20]}}}

Return only the JSON object, with no explanation and no code fences.

Document:
<<<
{numbered_document}
>>>
"""
