from django.db import migrations


def create_hnsw_index(apps, schema_editor):
    # No-op on non-Postgres backends (e.g. the sqlite test database) —
    # there's no HNSW/pgvector equivalent to create there, and
    # PgVectorRetriever is never selected on those backends anyway (see
    # apps.knowledge.retrieval.get_retriever()).
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunk_embedding_hnsw "
        "ON knowledge_chunk USING hnsw (embedding_vector vector_cosine_ops)"
    )


def drop_hnsw_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS knowledge_chunk_embedding_hnsw")


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0003_knowledgechunk_embedding_vector"),
    ]

    operations = [
        migrations.RunPython(create_hnsw_index, drop_hnsw_index),
    ]
