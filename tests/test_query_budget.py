import pytest
from django.db import connection


@pytest.mark.django_db
def test_query_budget_accepts_queries_below_limit(
    django_assert_max_num_queries,
):
    with django_assert_max_num_queries(3):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")


@pytest.mark.django_db
def test_query_budget_rejects_queries_above_limit(
    django_assert_max_num_queries,
):
    with pytest.raises(pytest.fail.Exception, match="Query budget exceeded"):
        with django_assert_max_num_queries(1):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.execute("SELECT 2")
