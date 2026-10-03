#!/usr/bin/env python
# coding: utf-8

# # Lane 1: Prompt Chaining
# 
# Owner: Jackson Kenyon. Development notebook; finished cells are copied into `notebook.ipynb` section 1 at assembly. See `docs/` and `setup.md`.

# In[1]:


import sys
sys.path.insert(0, "..")  # this notebook lives in dev/; make src/ importable

import importlib
from src import llm, tools
#importlib.reload(src.llm)
from src.llm import chat
from src.llm import handoff


# Ingest news, preprocess, classify, extract, summarize. Each stage uses the preceding stage's output.
# 
# **Contract:** `run_chain(symbol) -> {"Symbol": str, "articles": list[dict], "summary": str}`. The summary is one paragraph synthesized from all labeled articles.
# 
# **Demonstration:** run on AAPL from the cache and display the symbol and its combined news summary.

# In[ ]:


def ingest(symbol):
    # Stage 1: the plumbing does the fetching; this returns the cached articles.
    return tools.get_news(symbol)



def preprocess(articles: list[dict], nlp, max_tokens: int = 300) -> list[dict]:
    # Stage 2: no LLM. Deduplicate, strip, truncate. spaCy or plain Python.
    seen_titles = set()
    preprocessed_articles = []
    for article in articles:
        title=(article.get("title") or "").strip()
        summary=(article.get("summary") or "").strip()

        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        doc=nlp(summary if summary else title)

        tokens=[token.text for token in doc if not token.is_space]
        token_summary = doc[:max_tokens].text.strip()

        preprocessed_articles.append(
            {
                "title": title,
                "summary": token_summary,
                "publisher": article.get("publisher"),
                "published": article.get("published"),
                "url": article.get("url"),
            }
        )

    return preprocessed_articles

def classify(article: dict) -> dict:
    sentiment=["negative","neutral","positive"]
    topic=["earnings","news","market"]
    # Stage 3: one chat(..., json_mode=True) call per article -> {"sentiment", "topic"}.

    System=(
        "You are a financial analyst. Classify the given news article.\n"
        "Return a JSON object with exactly two keys:\n"
        '- "sentiment": one of "positive", "negative", or "neutral"\n'
        '- "topic": one of "earnings", "news", or "market"'
        )

    User=f"Title: {article['title']}\nSummary: {article['summary']}"

    output=chat(
        system=System,
        user=User,
        json_mode=True,
        temperature=0.0,
        agent="Chain"
    )

    return output
    #raise NotImplementedError


def extract(article, nlp):
    # Stage 4: entities and figures. spaCy NER (en_core_web_sm is installed) or one JSON call.
    title=article.get("title")
    summary=article.get("summary")
    title_doc=nlp(title)
    summary_doc=nlp(summary)

    title_entities = [(ent.text, ent.label_) for ent in title_doc.ents]
    summary_entities = [(ent.text, ent.label_) for ent in summary_doc.ents]

    output=[]
    output.append(title_entities)
    output.append(summary_entities)


    return output
    #raise NotImplementedError


def summarize(symbol, articles):
    # Stage 5: one chat() call over every labeled article -> one grounded paragraph.
    if not articles:
        return f"No news articles were available for {symbol}."

    article_sections = []
    for index, article in enumerate(articles, start=1):
        title = article.get("title") or "Untitled"
        summary = (article.get("summary") or "").strip() or "No summary provided."
        section = [f"{index}. {title}", f"Summary: {summary}"]
        if article.get("sentiment"):
            section.append(f"Sentiment: {article['sentiment']}")
        if article.get("topic"):
            section.append(f"Topic: {article['topic']}")
        if article.get("entities"):
            section.append(f"Entities: {article['entities']}")
        article_sections.append("\n".join(section))

    system = (
        "You are a careful financial news summarizer. Write exactly one concise paragraph "
        "of no more than five sentences synthesizing the supplied articles about the given symbol. "
        "Use only information in the articles, distinguish reported claims from established facts, "
        "and do not add predictions or investment advice."
    )
    user = f"Symbol: {symbol}\n\nArticles:\n" + "\n\n".join(article_sections)

    return chat(
        system=system,
        user=user,
        max_tokens=500,
        temperature=1,
        agent="Chain",
    )


def run_chain(symbol):
    # The function the agent calls. Runs the five stages in order.
    import spacy

    # Load spaCy model (disable unnecessary pipeline components for speed)
    nlp = spacy.load("en_core_web_sm", disable=["parser"])

    fetched_articles = ingest(symbol)
    articles = preprocess(fetched_articles, nlp)
    labeled_articles = []

    for article in articles:
        labeled_article = article.copy()
        labeled_article.update(classify(labeled_article))
        labeled_article["entities"] = extract(labeled_article, nlp)
        labeled_articles.append(labeled_article)

    summary = summarize(symbol, labeled_articles)
    return {
        "Symbol": symbol,
        "articles": labeled_articles,
        "summary": summary,
    }


# ## Demonstration
# 
# Run the function on cached data and produce the table and figure described above. Keep printed output narrow enough for a PDF page.
# 
# Put demo code inside the `if __name__ == "__main__":` block below. It runs normally in this notebook, but not when another lane imports this notebook's `.py` export, so importing your functions never re-runs your LLM calls and plots.

# In[20]:


if __name__ == "__main__":
    # demo code goes here, indented under this line

    df=run_chain("AAPL")
    print(df)
    pass

