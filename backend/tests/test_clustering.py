from datetime import datetime, timedelta, timezone

from app.clustering.service import cluster_articles
from app.clustering.similarity import jaccard, score, tokenize
from app.models.article import Article
from app.models.enums import Category, IranRelevance, StoryStatus
from app.models.story import Story, StoryArticle
from app.ranking.importance import score_importance
from app.ranking.service import rank_stories
from tests.conftest import make_source

NOW = datetime.now(timezone.utc)


def _article(db, source, title, url, hours_ago=1, desc=None, cat=Category.world):
    a = Article(
        source_id=source.id, source_name=source.name,
        article_url=url, title=title, description=desc,
        category=cat, hash=url, published_at=NOW - timedelta(hours=hours_ago),
    )
    db.add(a)
    db.commit()
    return a


# --- similarity unit tests ---
def test_tokenize_drops_stopwords():
    assert "iran" in tokenize("Iran and the US")
    assert "the" not in tokenize("Iran and the US")


def test_same_event_scores_above_unrelated():
    t1 = tokenize("Iran and US clash over Strait of Hormuz shipping")
    t2 = tokenize("Clashes reported near Strait of Hormuz as Iran tensions rise")
    t3 = tokenize("New AI model released for video generation")
    assert score(t1, t2, NOW, NOW) > score(t1, t3, NOW, NOW)
    assert jaccard(t1, t3) < 0.15


# --- clustering integration ---
def test_three_sources_one_event_collapse_to_one_story(db):
    s1 = make_source(db, name="Reuters")
    s2 = make_source(db, name="BBC")
    s3 = make_source(db, name="AJ")
    other = make_source(db, name="Verge")
    _article(db, s1, "Iran and US clash over Strait of Hormuz", "u1")
    _article(db, s2, "Clashes near Strait of Hormuz as Iran US tensions rise", "u2")
    _article(db, s3, "Iran US Strait of Hormuz clash reported", "u3")
    _article(db, other, "New AI video generation model released", "u4", cat=Category.ai)

    summary = cluster_articles(db)
    assert summary["new_stories"] == 2  # one Hormuz cluster + one AI story
    stories = db.query(Story).all()
    counts = sorted(s.source_count for s in stories)
    assert counts == [1, 3]  # 3-source event + 1-source event


def test_clustering_is_idempotent(db):
    s1 = make_source(db, name="Reuters")
    s2 = make_source(db, name="BBC")
    _article(db, s1, "Iran Hormuz shipping clash", "u1")
    _article(db, s2, "Iran Hormuz shipping clash reported", "u2")
    cluster_articles(db)
    n_links = db.query(StoryArticle).count()
    cluster_articles(db)  # re-run
    assert db.query(StoryArticle).count() == n_links  # nothing duplicated


def test_ranking_prefers_more_sources_and_flags_iran(db):
    # Event A: 3 sources, Iran-heavy.
    for i, name in enumerate(["Reuters", "BBC", "AJ"]):
        src = make_source(db, name=name)
        _article(db, src, "Iran Tehran Hormuz clash escalates", f"a{i}")
    # Event B: 1 source, unrelated.
    solo = make_source(db, name="Verge")
    _article(db, solo, "New smartphone chip unveiled", "b0", cat=Category.technology)

    cluster_articles(db)
    rank_stories(db)

    stories = sorted(db.query(Story).all(), key=lambda s: s.importance_score, reverse=True)
    top = stories[0]
    assert top.source_count == 3
    assert top.iran_relevance in (IranRelevance.high, IranRelevance.medium)
    assert stories[0].importance_score > stories[-1].importance_score


def test_importance_components_are_bounded():
    b = score_importance(
        distinct_sources=10, article_count=10, avg_reliability=1.0,
        hours_since_latest=0.0, iran_hits=9,
    )
    # each component is capped; total is near 100 for a maxed-out story
    assert b.independent_sources == 35
    assert b.recency == 20
    assert b.iran_relevance == 10
    assert 95 <= b.total <= 100


def test_admin_cluster_and_rank_endpoints(client, db):
    s1 = make_source(db, name="Reuters")
    s2 = make_source(db, name="BBC")
    _article(db, s1, "Iran Hormuz shipping clash", "u1")
    _article(db, s2, "Iran Hormuz shipping clash reported", "u2")
    assert client.post("/api/v1/admin/cluster").json()["new_stories"] == 1
    assert client.post("/api/v1/admin/rank").json()["ranked"] == 1
