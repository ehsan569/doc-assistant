# How it works, in plain words

You can use this as your interview cheat sheet. Read it with the code open.

## The one-sentence version

A question comes in, the system finds the few pieces of the DuckDB documentation most likely to contain the answer, hands only those pieces to a language model, and tells it to answer from them and to say "I couldn't find enough information" if they are not enough.

## The pipeline, one piece at a time

1. **Load and clean** (`src/docassist/loader.py`). The 20 pages are website source files with template code mixed in (headers, `{% link %}` tags, styling tags). The loader strips that so the model and the search see only readable text. There are tests that fail if any template code survives.
2. **Chunk** (`src/docassist/chunking.py`). Pages are too long to hand over whole, so each is cut into pieces of about 1000 characters. Two ways of cutting are compared: *fixed* (cut every ~1000 characters, with 150 overlap so a sentence at the edge is not lost) and *headings* (cut at section headings first, so a section stays together, and add "Page title > Section" in front of the text that is searched).
3. **Search** (`src/docassist/retrieve.py`). Two searchers:
   * *Keyword search (BM25)*: scores chunks by how many question words they contain, weighting rare words more. Fast, no model.
   * *Embedding search*: a small model turns each chunk and the question into a list of numbers that capture meaning; chunks whose numbers are closest to the question's are returned. Stored in Chroma.
   Both return the top k chunks (default 5) with a score.
4. **Answer** (`src/docassist/generate.py`). The question and the chunks go to the model, which must reply in a fixed shape: whether it can answer, the answer, and which chunk ids it used. The code then checks the ids: any id that was not actually supplied is dropped and reported. An answer with no valid citation is flagged.
5. **Show** (`app.py`). The answer on the left, the retrieved chunks on the right with links to the real pages, and a tick on the chunks the answer cited. The app works without an API key (it then shows retrieval only).

## The evaluation (the part that makes this a project, not a demo)

* `eval/questions.jsonl`: 30 questions. 20 have answers in the pages (with the exact sentence that proves it), 6 are about topics the pages never mention, 4 are "near misses" that sound answerable but are not (for example, a maximum number of columns).
* `eval/verify_questions.py` checks by script that every proof sentence really is in the page and every "unanswerable" topic really is absent.
* **Retrieval is measured alone** (`run_retrieval_eval.py`): is the right page in the top 1, 3, 5? Does a top chunk contain the proof sentence? No language model is involved, so a miss here is a search problem.
* **Answers are measured separately** (`run_answer_eval.py`): each result is sorted into "search missed and the model refused", "search missed and the model answered anyway", "model refused although the evidence was there", "answered", "correctly refused", "should have refused". This is how you tell *search failed* from *the model failed*.
* Whether an answer is correct is a human call. You fill in a `human_correct` column. Until you do, no accuracy figure appears anywhere.

## What the numbers say so far (keyword search only)

Keyword search found the right page in the top 3 for every answerable question, but put the right *sentence* first less often. Two real misses are worth knowing by heart:

* "How many rows are sampled when detecting CSV types?" A different CSV page has a whole section called Sample Size, so it outranked the page that states the default.
* "How much smaller was storage when the timestamp column was ordered?" The right page came first, but the sentence sat in the second chunk.

Embedding search and the answer evaluation have not been run yet. The README says so.

## Questions an interviewer may ask, and honest answers

* *Why two chunking strategies?* Because chunk boundaries decide whether the answer sentence lands in a retrievable piece. I measured it instead of guessing. Note the two strategies differ in boundaries **and** the breadcrumb, so I cannot say which one caused a difference.
* *Why keyword search as well as embeddings?* A baseline. If a model-based search does not beat plain keyword matching on this corpus, the extra complexity is not earned.
* *How do you know it is right?* I do not, from the system alone. Retrieval is scored against sentences I verified in the pages; answer correctness is judged by me; and I report how many answers I labelled.
* *What is the biggest weakness?* The questions were written while looking at the pages, so they share words with the pages. That flatters keyword search. The fix is to add questions written from memory by someone who has not read the page.
* *What did you build with AI help?* Be straightforward: the code and the first draft of the questions were written with Claude. Only say you can explain every module after you have read this file with the code open and run the tests and evaluations yourself.

## Where to look when something is wrong

| Symptom | Look at |
|---|---|
| Strange text in a chunk | `loader.py`, then `python -m src.docassist.search "..."` |
| Right page, wrong passage | `eval/results/retrieval_per_question.csv` (evidence_rank) |
| Model answered when it should not have | `answer_results.csv`, outcome `should_have_refused` or `retrieval_miss_answered` |
| Citation missing or odd | `invalid_citations` and `uncited` columns |
