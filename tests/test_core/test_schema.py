"""Tests for schema loading and L2 tag resolution."""

from synterr.schemas import FineGrainedTag, load_schema


class TestRozentalSchemaLoading:
    """Test that rozental.yaml loads correctly with L2 tags."""

    def setup_method(self):
        self.schema = load_schema("rozental")

    def test_basic_loading(self):
        assert self.schema.name == "rozental"
        assert len(self.schema.primary_tags) == 29

    def test_fine_grained_tags_loaded(self):
        """L2 tags should be parsed from fine_grained_tags section."""
        assert len(self.schema.fine_grained_tags) > 0
        # Check a few known L2 tags
        assert "sp_root_checked" in self.schema.fine_grained_tags
        assert "mo_noun_case_gen_a_u" in self.schema.fine_grained_tags
        assert "pu_clause_subordinate" in self.schema.fine_grained_tags

    def test_fine_grained_tag_structure(self):
        tag = self.schema.fine_grained_tags["sp_root_checked"]
        assert isinstance(tag, FineGrainedTag)
        assert tag.parent == "sp_root"
        assert tag.paras == "§1"
        assert "unstressed" in tag.description.lower()

    def test_fine_grained_tag_parent_exists(self):
        """Every L2 tag's parent should be a valid L1 tag."""
        for name, tag in self.schema.fine_grained_tags.items():
            assert tag.parent in self.schema.primary_tags, (
                f"L2 tag {name} has parent {tag.parent} not in primary_tags"
            )


class TestL2Mappings:
    """Test L2 tag resolution from handler subtypes."""

    def setup_method(self):
        self.schema = load_schema("rozental")

    # --- Spelling subtypes ---

    def test_vowel_reduction_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("vowel_reduction") == "sp_root_checked"
        )

    def test_devoicing_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("devoicing")
            == "sp_root_voiced_voiceless"
        )

    def test_double_consonant_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("double_consonant") == "sp_root_double"
        )

    def test_cluster_l2(self):
        assert self.schema.get_l2_tag_for_subtype("cluster") == "sp_root_silent"

    def test_keyboard_no_l2(self):
        """keyboard errors are random typos, no specific Rozental L2 tag."""
        assert self.schema.get_l2_tag_for_subtype("keyboard") is None

    def test_soft_sign_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("soft_sign") == "sp_affix_hard_soft_sign"
        )

    def test_prefix_voicing_l2(self):
        assert self.schema.get_l2_tag_for_subtype("prefix_voicing") == "sp_affix_prefix"

    def test_tsa_confusion_l2(self):
        assert self.schema.get_l2_tag_for_subtype("tsa_confusion") == "sp_verb_endings"

    # --- Orthographic spelling subtypes ---

    def test_pre_pri_l2(self):
        assert self.schema.get_l2_tag_for_subtype("pre_pri") == "sp_affix_prefix"

    def test_vowel_after_ts_l2(self):
        assert self.schema.get_l2_tag_for_subtype("vowel_after_ts") == "sp_pos_sibilant"

    def test_vowel_after_sibilant_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("vowel_after_sibilant")
            == "sp_pos_sibilant"
        )

    def test_participle_suffix_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("participle_suffix")
            == "sp_participle_endings"
        )

    def test_suffix_enk_onk_l2(self):
        assert self.schema.get_l2_tag_for_subtype("suffix_enk_onk") == "sp_noun_endings"

    def test_suffix_insk_ensk_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("suffix_insk_ensk") == "sp_adj_suffixes"
        )

    # --- Function spelling subtypes ---

    def test_ne_attachment_l2(self):
        assert self.schema.get_l2_tag_for_subtype("ne_attachment") == "sp_ne_ni"

    def test_conjunction_split_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("conjunction_split")
            == "sp_conjunction_spelling"
        )

    def test_taki_hyphen_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("taki_hyphen") == "sp_particle_spelling"
        )

    # --- Morphological subtypes ---

    def test_noun_case_l2(self):
        assert self.schema.get_l2_tag_for_subtype("noun_case") == "mo_noun_case_other"

    def test_adj_case_maps_to_agreement(self):
        """2026-07-08: adj grammeme handlers map to ag_mn_agreement — the
        learner-heartland home Rozental's native taxonomy lacked."""
        assert self.schema.get_l2_tag_for_subtype("adj_case") == "ag_mn_agreement"

    def test_adj_gender_maps_to_agreement(self):
        assert self.schema.get_l2_tag_for_subtype("adj_gender") == "ag_mn_agreement"

    def test_verb_person_number_maps_to_agreement(self):
        """2026-07-08: see adj_case note."""
        assert (
            self.schema.get_l2_tag_for_subtype("verb_person_number")
            == "ag_sv_agreement"
        )

    # --- Lexical/structural subtypes ---

    def test_paronym_l2(self):
        assert self.schema.get_l2_tag_for_subtype("paronym") == "lx_paronym"

    def test_preposition_l2(self):
        assert self.schema.get_l2_tag_for_subtype("preposition") == "gv_prep_choice"

    def test_word_omission_l2(self):
        assert self.schema.get_l2_tag_for_subtype("word_omission") == "lx_word_missing"

    def test_word_insertion_l2(self):
        assert self.schema.get_l2_tag_for_subtype("word_insertion") == "lx_word_extra"

    # --- Punctuation subtypes ---

    def test_comma_subordinate_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("comma_subordinate")
            == "pu_clause_subordinate"
        )

    def test_comma_homogeneous_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("comma_homogeneous")
            == "pu_comma_homogeneous"
        )

    def test_pair_participle_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("pair_participle")
            == "pu_comma_isolation"
        )

    def test_dash_subj_pred_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("dash_subj_pred") == "pu_dash_subj_pred"
        )

    def test_comma_before_kak_l2(self):
        assert (
            self.schema.get_l2_tag_for_subtype("comma_before_kak")
            == "pu_clause_comparative"
        )


class TestL2TagConsistency:
    """Test that all L2 mappings point to valid L2 tags."""

    def setup_method(self):
        self.schema = load_schema("rozental")

    def test_all_l2_tags_exist(self):
        """Every l2_tag in mappings must exist in fine_grained_tags."""
        for subtype, mapping in self.schema.mappings.items():
            if mapping.l2_tag is not None:
                assert mapping.l2_tag in self.schema.fine_grained_tags, (
                    f"Mapping {subtype} → l2_tag={mapping.l2_tag} "
                    f"not found in fine_grained_tags"
                )

    def test_l2_tag_parent_matches_primary(self):
        """L2 tag's parent (L1 tag) should match the mapping's primary tag."""
        for subtype, mapping in self.schema.mappings.items():
            if mapping.l2_tag is not None:
                fg = self.schema.fine_grained_tags[mapping.l2_tag]
                assert fg.parent == mapping.primary, (
                    f"Mapping {subtype}: l2_tag {mapping.l2_tag} has parent "
                    f"{fg.parent} but mapping primary is {mapping.primary}"
                )


class TestRlcSchemaNoL2:
    """Test that schemas without fine_grained_tags work fine."""

    def test_rlc_has_no_fine_grained(self):
        schema = load_schema("rlc")
        assert len(schema.fine_grained_tags) == 0

    def test_rlc_l2_returns_none(self):
        schema = load_schema("rlc")
        assert schema.get_l2_tag_for_subtype("vowel_reduction") is None
