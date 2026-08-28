from contextlib import contextmanager

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext


@pytest.fixture
def django_assert_max_num_queries():
    """
    Assert that a code block executes no more than `max_queries` SQL queries.

    Usage:

        with django_assert_max_num_queries(10):
            response = client.get("/some/url/")
    """

    @contextmanager
    def assert_max_queries(max_queries):
        with CaptureQueriesContext(connection) as captured:
            yield captured

        actual = len(captured)

        if actual > max_queries:
            sql = "\n\n".join(
                f"{index + 1}. {query['sql']}"
                for index, query in enumerate(captured.captured_queries)
            )

            pytest.fail(
                f"Query budget exceeded: "
                f"expected <= {max_queries}, executed {actual}.\n\n"
                f"Captured SQL:\n{sql}"
            )

    return assert_max_queries
