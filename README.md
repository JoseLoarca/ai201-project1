# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

I chose student reviews of CS professors and courses at University of the People. This knowledge is valuable because 
students can benefit from these reviews to anticipate the difficulty level of courses before they start. This knowledge 
is also hard to find through official channels as University of the People is an online school that is very different
from traditional colleges. Each term you might end up with different classmates, which makes socialization hard and 
therefore knowledge sharing in terms of courses / professors is limited to platforms like Reddit or RateMyProfessor which
not all students use.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

For this occasion, I'll be working with .txt documents stored locally. This helps me avoid complicated processes like
web scraping or extracting text from unstructured PDF files.

| #  | Source                             | Description                                                                                                                   | URL or location                                                      |
|----|------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| 1  | RateMyProfessor                    | Reviews for Computer Science Professor Alejandro                                                                              | /documents/ratemyprofessor/alejandro.txt                             |
| 2  | RateMyProfessor                    | Reviews for Computer Science Professor Andrea                                                                                 | /documents/ratemyprofessor/andrea.txt                                |
| 3  | RateMyProfessor                    | Reviews for Computer Science Professor Cecil                                                                                  | /documents/ratemyprofessor/cecil.txt                                 |
| 4  | RateMyProfessor                    | Reviews for Computer Science Professor Charles                                                                                | /documents/ratemyprofessor/charles.txt                               |
| 5  | RateMyProfessor                    | Reviews for Computer Science Professor Matthew                                                                                | /documents/ratemyprofessor/matthew.txt                               |
| 6  | RateMyProfessor                    | Reviews for Computer Science Professor Mudasir                                                                                | /documents/ratemyprofessor/mudasir.txt                               |
| 7  | RateMyProfessor                    | Reviews for Computer Science Professor Romana                                                                                 | /documents/ratemyprofessor/romana.txt                                |
| 8  | RateMyProfessor                    | Reviews for Computer Science Professor Ubaid                                                                                  | /documents/ratemyprofessor/ubaid.txt                                 |
| 9  | RateMyProfessor                    | Reviews for Computer Science Professor William                                                                                | /documents/ratemyprofessor/william.txt                               |
| 10 | Reddit (r/uopeople)                | Reddit post on which CS courses where the most difficult per personal experiences.                                            | /documents/reddit/cs_classes_you_found_them_difficult.txt            |
| 11 | Reddit (r/uopeople)                | Reddit post on which CS courses where the most difficult per personal experiences.                                            | /documents/reddit/how_to_make_the_most_out_of_your_bachelor_in.txt   |
| 12 | Reddit (r/uopeople)                | Reddit post from alumni with tips and tricks on how to make the most out of a CS degree at UoPeople.                          | /documents/reddit/what_were_your_most_difficult_computer_science.txt |
| 13 | University of the People's Catalog | Official UoPeople document with information about the CS degree such as degree description, prerequisites, learning pathways. | /documents/uop/bscs_uopeople_catalog.txt                             |
| 14 | University of the People's Catalog | Official UoPeople document with a list of CS courses, their description and prerequisites.                                    | /documents/uop/courses_in_computer_science.txt                       |


---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

I have 3 different categories (or sources) of documents. Each category comes with different content structure which means
each category needs a different chunking strategy.

- #### RateMyProfessor reviews
    For these reviews I will use **semantic** chunking. Semantic chunking is the best option, in my opinion, as each student 
review is a different semantic unit, so the topic boundary is clear. 
<br><br>
    The challenge to solve with semantic chunking is context loss. The professor information is only found at the beginning 
of each document. So usually reviews don't mention the professor name at all. A good approach to fix this is to inject
metadata to each review before chunking. The metadata would include, at the very least, the professor name and their rating.
<br><br>
    For this semantic approach I won't need to configure a specific chunk size or overlap.

- #### Reddit posts
    Reddit posts very in terms of length and comments. Some posts don't include body, just a title, while others have a long,
detailed body. Comments vary in character length, as well as hierarchy, as some posts include nested replies.
<br><br>
    For these posts I will be using a **recursive** approach. The reasoning behind using recursive chunking for this category,
is to try and preserve the natural boundaries of posts and comments. Recursive chunking should respect natural boundaries
for posts and comments. Which means it should be able to handle long posts and short comments gracefully. For Reddit posts
I will use a **chunk size of 256 tokens**, with an **overlap of 26 tokens**.

- #### UoPeople Catalog
    For documents from the UoPeople catalog I will be using a hybrid approach. I have two different documents: one is a long
    document with a list of all the CS courses, and the other one is a more descriptive document that includes information
    about the degree, learning pathways, prerequisites, etc.
<br><br>
    For the course list, I will use a **structure-based** chunking. With this approach, I will be treating each course as one 
    chunk unit. For this approach I don't need to set a specific chunk size or overlap.
    <br><br>
    Now for the other document, I will use **recursive** chunking. The idea is to try to preserve units like 
    "learning pathways" as  one chunk.  I will be using a **chunk size of 256 tokens** with an **overlap of 26 tokens**. 
    A token size in recursive chunking is used to ensure that chunks don't exceed  this size, so in the end I might 
    end up getting chunks of different sizes, but never greater than 256 tokens.

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** all-MiniLM-L6-v2 via sentence-transformers

**Production tradeoff reflection:** If cost wasn't a constraint, I would evaluate different embedding models. 

For example, all-MiniLM-L6-v2 is a simple model with a 256 token maximum capacity. Assuming eventually I will handle larger
documents, a model with a higher maximum token capacity could be useful. 

I would also evaluate using a different and more powerful domain-specific model. For example: a model trained on
question-to-answer style interactions would be better at interpreting the queries. 

A model with multilingual support could be useful as well. Given
that University of the People is a college with students from all around the world, there might be additional resources
in different languages, or real users could ask questions in their native languages.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:** this is an excerpt of the rules I have to the LLM in terms of grounding:

>Rules you must follow:
>1. Answer ONLY using information present in the provided context. Do not use any outside knowledge.
>2. Every claim you make must be traceable to a specific source. Always cite the source file(s) in your answer, for example: (ratemyprofessor: alejandro.txt) or (courses_in_computer_science.txt).
>3. If the context does not contain enough information to answer the question, respond with exactly: "I don't have enough information on that."
>4. Do not speculate, infer, or fill gaps with general knowledge.
>5. Be concise and direct. Do not repeat yourself.

**How source attribution is surfaced in the response:** the context was formatted in the following format:
>CONTEXT:<br>
>[Source: FILENAME]<br>
>CHUNK TEXT<br><br>
>[Source: FILENAME]<br>
>CHUNK TEXT

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question                                                            | Expected answer                                                                                                                                                                                                                                                                                                                                               | System response (summarized)                                                                                                                                                                                                                                                                                                                                                                                                                                           | Retrieval quality | Response accuracy |
|---|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|-------------------|
| 1 | Are there any courses on databases in this degree?                  | Yes, in this degree you will find Databases 1 and Databases 2 which cover everything related to databases. Source: courses_in_computer_science.txt                                                                                                                                                                                                            | Yes, there are courses on databases in the Bachelor of Science in Computer Science degree. Specifically, the courses are Databases 1 (CS2203) and Databases  2 (CS3306) (courses_in_computer_science.txt). The degree program also mentions "database management" as one of the areas of study (bscs_uopeople_catalog.txt).                                                                                                                                            | Relevant          | Accurate          |
| 2 | Has anyone ever encountered any professors that good give feedback? | Yes, many students have noted that professors such as Alejandro, Andrea, and William give good feedback. Source: alejandro.txt, andrea.txt, william.txt                                                                                                                                                                                                       | Yes, according to the reviews, both Professor Alejandro Lara (alejandro.txt) and Professor Matthew Booth (matthew.txt) are known to give good feedback. Specifically, the reviews for Professor Matthew Booth mention "GIVES GOOD FEEDBACK" as a tag in two separate reviews (matthew.txt), and a review for  Professor Alejandro Lara mentions that he "answers your questions" and "gives good feedback" is implied by the tag "GIVES GOOD FEEDBACK" (alejandro.txt) | Relevant          | Accurate          |
| 3 | What is CS4407 about?                                               | CS4407, also known as Data Mining and Machine Learning, is a proctored course that covers machine learning, knowledge discovery, and data mining. Source: courses_in_computer_science.txt, bscs_uopeople_catalog.txt                                                                                                                                          | CS4407, Data Mining and Machine Learning, is about introducing current concepts in machine learning, knowledge discovery, and data mining, and also discusses approaches to the analysis of learning algorithm performance. (courses_in_computer_science.txt)                                                                                                                                                                                                          | Relevant          | Accurate          |
| 4 | Is CS2204 a difficult course?                                       | CS2204 is considered to be a difficult course per some students. Reviews for professors that have taught this course have an average of 3.5/5 for difficulty. Source: cs_classes_you_found_them_difficulty.txt, cecil.txt                                                                                                                                     | Yes, CS2204 is considered a difficult course. According to [Privat3Ice] in (cs_classes_you_found_them_difficult.txt), it has a "heavy workload, difficult material, [and an] impossible final exam". Additionally, [Dry_Patience872] in the same source also lists CS 2204 Networking 1 as one of the hardest courses they faced.                                                                                                                                      | Relevant          | Accurate          |
| 5 | Are there any tips for passing CS1102?                              | CS1102, also known as Programming 2, is a course that covers Java beyond its basic concepts. Students have recommended watching YouTube tutorials as the textbook quality is low, another useful tip is to go through the Oracle docs to expand your knowledge in Java. Source: courses_in_computer_science, how_to_make_the_most_out_of_your_bachelor_in.txt | Yes, there are tips for passing CS1102. According to the post "How to make the most out of your bachelor in Computer Science at UoPeople" (how_to_make_the_most_out_of_your_bachelor_in.txt), tips for this course include: watching YouTube tutorials, going through the Oracle docs to get practice navigating them, and using a complicated programming assignment as a starting point for a project.                                                               | Relevant          | Accurate          |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** What do reviews about Charles Chery say?

**What the system returned:** I don't have enough information on that.

**Root cause (tied to a specific pipeline stage):** When determining the question intent, the wrong metadata filters are 
set for this specific type of question. This causes that the returned chunks are completely unrelated to the question. 

If the question intent was being determined correctly, the chunks returned would be accurate.
As right now, if I ask: What do reviews **_for_** Charles Chery say?, I do get a relevant and accurate answer. Notice 
how the only difference is I used **_for_** instead of **_about_**.

**What you would change to fix it:** The bug is clear in determine_question_intent(), **_about_** is considered to be a
keyword for questions related specifically to courses, so the wrong filter is being applied.

The change seems to be as easy as removing the **_about_** keyword from the course-related keywords list.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:** the Chunking Strategy spec made it easy to get started with the 
project. The requirements were clear and detailed, so I didn't have to do any updates to my chosen strategies during the
development. 

**One way your implementation diverged from the spec, and why:** the retrieval step got slighlty complicated during the 
development. I was originally planning to use a different LLM (Gemma 4 via Ollama) to determine the question intent.
I had to change this as I was told that I should avoid using other tools / models. I reverted to determining
the question intent using keyword matching. 

After this, I also had to fix a few issues related to not getting relevant chunks. This fix basically consisted
on reranking results for specific questions, something I wasn't planning on initially.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*<br>
I gave Claude my Embedding section from planning.md and asked it to generate scaffold code.
- *What it produced:*<br>
An embedding logic that would chunk and embed on each run, regardless of a ChromaDB collection already existing.
- *What I changed or overrode:*<br>
I directed it to update the logic so that the chunking and embedding would only occur if: a ChromaDB collection does 
not exist, OR a FORCE_REBUILD environment variable exists and is set to True.

**Instance 2**

- *What I gave the AI:*<br>Based on my planning.md, I asked Claude to implement an entry point file (app.py). App.py was in
charge of orchestrating each step (ingestion, chunking, embedding, retrieval, generation, and interface). I was
testing manually, so this orchestrator came in handy to verify the results of the retrieval stage when there was no 
generation or interface implementation, for example.
- *What it produced:*<br> An app.py file with scaffold code for each stage. It even included scaffolding for a Gradio UI interface.
- *What I changed or overrode:*<br>I changed the interface step, as I didn't want to use Gradio and instead decided to use 
a simple CLI interface.
