from __future__ import annotations


def test_aoasis_namespace_exposes_variant_identity_and_core_apis():
    import oasis
    from oasis import aoasis
    from oasis.aoasis import (
        AOASIS_VARIANT_NAME,
        AtherumPopulationStore,
        build_default_population,
    )

    assert AOASIS_VARIANT_NAME == "A-Oasis"
    assert aoasis.AOASIS_VARIANT_NAME == "A-Oasis"
    assert oasis.AOASIS_VARIANT_NAME == "A-Oasis"
    assert oasis.AtherumPopulationStore is AtherumPopulationStore
    assert callable(build_default_population)


def test_atherum_namespace_remains_a_compatibility_alias():
    from oasis import aoasis
    from oasis import atherum

    assert atherum.AOASIS_VARIANT_NAME == aoasis.AOASIS_VARIANT_NAME
    assert atherum.AtherumPopulationStore is aoasis.AtherumPopulationStore
    assert atherum.build_default_population is aoasis.build_default_population
