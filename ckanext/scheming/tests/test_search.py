"""
Search over datasets whose fields come from a scheming schema.

Scheming stores its custom fields as dataset extras, so they reach the
search index as ``extras_<field>``; repeating subfields are serialized to
JSON by ``scheming_nerf_index`` before indexing. These tests check that
package_search filters, facets, sorts and full text search work over
those fields with the search backend in use.
"""
import pytest
from ckan.tests.helpers import call_action
from ckan.tests import factories


@pytest.fixture
def camels():
    org = factories.Organization()
    a = factories.Dataset(
        type="test-schema", name="alf", title="Alf the camel",
        owner_org=org["id"], humps="1", category="bactrian",
        personality=["friendly", "spits"], a_relevant_date="2020-01-15",
        notes="a dromedary that lives in the desert",
    )
    b = factories.Dataset(
        type="test-schema", name="bert", title="Bert the camel",
        owner_org=org["id"], humps="2", category="black",
        personality=["friendly"], a_relevant_date="2024-06-30",
        notes="a camel from the mountains",
    )
    c = factories.Dataset(
        type="test-subfields", name="cite", title="Dataset with citations",
        owner_org=org["id"],
        citation=[{"originator": ["Alice", "Bob"],
                   "publication_date": "2019-03-01"}],
        contact_address=[{"address": "1 Main St", "city": "Ottawa",
                          "state": "ON", "postal_code": "K1A"}],
    )
    return a, b, c


@pytest.mark.usefixtures("clean_db", "clean_index", "with_plugins")
class TestSearchSchemingFields(object):

    def test_filter_by_dataset_type(self, camels):
        r = call_action("package_search", fq="dataset_type:test-subfields")
        assert [d["name"] for d in r["results"]] == ["cite"]

    def test_filter_by_custom_field(self, camels):
        r = call_action("package_search", fq="extras_category:black")
        assert [d["name"] for d in r["results"]] == ["bert"]

    def test_filter_by_multiple_choice_field(self, camels):
        r = call_action("package_search", fq='extras_personality:"spits"')
        assert [d["name"] for d in r["results"]] == ["alf"]
        r = call_action("package_search", fq='extras_personality:"friendly"')
        assert sorted(d["name"] for d in r["results"]) == ["alf", "bert"]

    def test_filter_by_date_range(self, camels):
        r = call_action(
            "package_search",
            fq="extras_a_relevant_date:[2021-01-01T00:00:00Z TO *]")
        assert [d["name"] for d in r["results"]] == ["bert"]

    def test_custom_field_in_q(self, camels):
        r = call_action("package_search", q="humps:2")
        assert [d["name"] for d in r["results"]] == ["bert"]

    def test_free_text_finds_custom_field_values(self, camels):
        # category is an extra: its value is part of the indexed text
        r = call_action("package_search", q="black")
        assert sorted(d["name"] for d in r["results"]) == ["bert"]

    def test_free_text_finds_repeating_subfield_values(self, camels):
        r = call_action("package_search", q="Ottawa")
        assert [d["name"] for d in r["results"]] == ["cite"]

    def test_facet_on_custom_field(self, camels):
        r = call_action("package_search", q="camel",
                        **{"facet.field": ["extras_category"]})
        assert r["facets"]["extras_category"] == {"bactrian": 1,
                                                  "black": 1}

    def test_sort_by_custom_field(self, camels):
        r = call_action("package_search", fq="dataset_type:test-schema",
                        sort="extras_humps desc")
        assert [d["name"] for d in r["results"]] == ["bert", "alf"]

    def test_subfields_come_back_intact(self, camels):
        r = call_action("package_search", fq="name:cite")
        d = r["results"][0]
        assert d["citation"][0]["originator"] == ["Alice", "Bob"]
        assert d["contact_address"][0]["city"] == "Ottawa"
