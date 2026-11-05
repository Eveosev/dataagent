"""Round 7 regression: Chinese negated comparisons must state one direction.

Round 6 fixed the English reversal (``"above"`` vs ``"below"``) by comparing
``(direction, number)`` pairs, but the Chinese patterns still let a negated
phrase contribute *both* directions: ``"不超过5000元"`` contains ``"超过"`` and
``"不低于5000元"`` contains ``"低于"``.  The anchor therefore exported
``("lower", 5000)`` **and** ``("upper", 5000)``, so a condition claiming the
opposite direction matched the extra bound and was silently accepted with
``issues=[]`` -- plan §5 step 3 / §10 item 2 require an unsupported value to be
downgraded, never reversed.

The fix consumes the negated phrase before the bare-direction patterns, so
each anchor states exactly one bound.  These tests pin both the bound parser
and the atomic entry point that the Tester used.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from conftest import call
from dataagent_contracts.core import (
    AssetRef,
    DocumentRef,
    SourceAnchor,
    VersionedRef,
)
from dataagent_data.contracts.layer import DocumentContent, PageContent
from dataagent_data.anchors import (
    _comparison_bounds,
    _comparison_scope_is_ambiguous,
    anchor_supports_text,
)


def _anchor(anchor_text: str) -> SourceAnchor:
    return SourceAnchor(
        source_ref="file:cn",
        source_revision="r1",
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(anchor_text),
        },
    )


def _define_rule(runtime, ctx, anchor_text: str, condition_text: str):
    """Invoke ``define_business_rules`` with a bare Chinese anchor document."""

    blocks_ref = runtime.content.put(
        DocumentContent(
            pages=[PageContent(page=1, text=anchor_text)]
        ).model_dump(mode="json")
    )
    document = DocumentRef(
        # r32-gov B1: the document asset must be digest-bound to its blocks
        # (every product parse path already is; see load_document_content).
        asset=AssetRef(
            id="asset:cn",
            kind="document",
            scope_ref="tenant:test/project:p1",
            revision=blocks_ref,
            resolver="local_content",
            locator=blocks_ref,
            digest=blocks_ref,
        ),
        original_ref=VersionedRef(id="file:cn", revision="r1"),
        content_type="text",
        blocks_ref=blocks_ref,
        page_count=1,
    )
    # Locally built documents must register their source binding so that
    # load_document_content accepts them (reviewer F1 fail-closed rule).
    from dataagent_data.preparation.documents import register_document_blocks

    register_document_blocks(runtime, document)
    return call(
        "define_business_rules",
        {
            "statement": "threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": condition_text,
                        "anchors": [_anchor(anchor_text)],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )


def _resolver(anchor_text: str) -> DocumentContent:
    return DocumentContent(pages=[PageContent(page=1, text=anchor_text)])


@pytest.mark.parametrize(
    ("phrase", "direction"),
    [
        ("超过5000元", "upper"),
        ("不低于5000元", "upper"),
        ("不少于5000元", "upper"),
        ("不得低于5000元", "upper"),
        ("未低于5000元", "upper"),
        ("低于5000元", "lower"),
        ("不超过5000元", "lower"),
        ("不高于5000元", "lower"),
        ("不得超过5000元", "lower"),
        ("未超过5000元", "lower"),
        ("没有超过5000元", "lower"),
        ("不允许超过5000元", "lower"),
        ("不准超过5000元", "lower"),
        ("禁止超过5000元", "lower"),
        ("不得高于5000元", "lower"),
        ("未达到5000元", "lower"),
        ("达不到5000元", "lower"),
        ("不到5000元", "lower"),
        ("5000元以上", "upper"),
        ("5000元以下", "lower"),
    ],
)
def test_chinese_comparison_states_exactly_one_direction(phrase, direction):
    assert _comparison_bounds(phrase) == {(direction, Decimal(5000))}


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("不超过5000元", "超过5000元"),
        ("不超过5000元", "5000元以上"),
        ("不低于5000元", "低于5000元"),
        ("不低于5000元", "5000元以下"),
        ("不高于5000元", "高于5000元"),
        ("不少于5000元", "少于5000元"),
        ("不得低于5000元", "低于5000元"),
        ("不得超过5000元", "超过5000元"),
        ("未超过5000元", "超过5000元"),
        ("没有超过5000元", "超过5000元"),
        ("不允许超过5000元", "超过5000元"),
        ("禁止超过5000元", "超过5000元"),
        ("不得高于5000元", "高于5000元"),
        ("未达到5000元", "超过5000元"),
        ("不到5000元", "超过5000元"),
    ],
)
def test_reversed_chinese_condition_is_not_supported(anchor_text, condition_text):
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert reason, (anchor_text, condition_text)


@pytest.mark.parametrize(
    "phrase",
    [
        "不超过5000元",
        "不低于5000元",
        "不得低于5000元",
        "不得超过5000元",
    ],
)
def test_same_chinese_condition_is_still_supported(phrase):
    assert (
        anchor_supports_text(_resolver(phrase), _anchor(phrase), phrase) == ""
    )


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # The exact probes the Tester used against the atomic entry.
        ("不超过5000元", "超过5000元"),
        ("不低于5000元", "低于5000元"),
        ("超过5000元", "低于5000元"),
    ],
)
def test_rule_atom_rejects_reversed_chinese_condition(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)
    assert "da03.unanchored_condition" in codes, (condition_text, codes)


def test_rule_atom_accepts_the_matching_chinese_condition(runtime, ctx):
    result = _define_rule(runtime, ctx, "超过5000元", "超过5000元")
    assert result.status.value == "ok", result.issues
    assert result.data is not None
    condition = result.data.draft.definition.conditions[0]
    assert condition.text == "超过5000元"


# Round 8: the negator can be separated from the direction word by an adverb
# ("未明显超过", "不得擅自低于"). The negated patterns are a finite list and do
# not cover that shape, so the bare patterns used to read the anchor as a
# *positive* bound and accept the reverse. The parser now treats an unconsumed
# negator in the lookback window as ambiguous, drops the bound, and the anchor
# rejects every condition instead of guessing (fail-closed).
_ADVERB_NEGATION_CASES = [
    ("未明显超过5000元", "超过5000元"),
    ("没有明显超过5000元", "超过5000元"),
    ("未大幅超过5000元", "超过5000元"),
    ("未显著低于5000元", "低于5000元"),
    ("不得明显高于5000元", "高于5000元"),
    ("不得擅自低于5000元", "低于5000元"),
    ("不得随意超过5000元", "超过5000元"),
]


@pytest.mark.parametrize("phrase", [case[0] for case in _ADVERB_NEGATION_CASES])
def test_ambiguous_negated_scope_does_not_guess_a_bound(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(("anchor_text", "condition_text"), _ADVERB_NEGATION_CASES)
def test_negator_adverb_direction_is_not_reversed(anchor_text, condition_text):
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert reason, (anchor_text, condition_text)
    assert "ambiguous" in reason, (anchor_text, condition_text, reason)


@pytest.mark.parametrize(("anchor_text", "condition_text"), _ADVERB_NEGATION_CASES)
def test_rule_atom_rejects_ambiguous_negated_scope(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)
    assert "da03.unanchored_condition" in codes, (condition_text, codes)


def test_ambiguous_scope_rejects_a_verbatim_condition_too():
    anchor_text = "未明显超过5000元"
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), anchor_text
    )
    assert "ambiguous" in reason, reason


def test_negator_in_an_earlier_clause_does_not_poison_the_comparison():
    anchor_text = "不适用；超过5000元"
    assert (
        anchor_supports_text(_resolver(anchor_text), _anchor(anchor_text), "超过5000元")
        == ""
    )


def test_negation_scope_scan_is_not_a_fixed_window():
    # An insertion can be longer than any constant; the scan stops at the
    # clause boundary instead, so this is still fail-closed.
    anchor_text = "不得以任何形式超过5000元"
    assert _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), "超过5000元"
    )
    assert "ambiguous" in reason, reason


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("未明显不足5000元", "低于5000元"),
        ("并未明显不足5000元", "低于5000元"),
        ("不得不超过5000元", "超过5000元"),
    ],
)
def test_double_negated_lexical_form_is_fail_closed(anchor_text, condition_text):
    assert _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert "ambiguous" in reason, reason


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("禁止以任何形式超过5000元", "超过5000元"),
        ("是否超过5000元", "超过5000元"),
    ],
)
def test_imperative_or_question_prefix_is_fail_closed(anchor_text, condition_text):
    assert _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert "ambiguous" in reason, reason


def test_unrelated_negator_does_not_poison_a_direct_condition():
    # "未经批准" scopes over approval, not over the comparison; this is a
    # direct condition and stays grounded.
    anchor_text = "未经批准不得低于5000元"
    assert _comparison_bounds(anchor_text) == {("upper", Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(anchor_text)
    assert (
        anchor_supports_text(
            _resolver(anchor_text), _anchor(anchor_text), "不得低于5000元"
        )
        == ""
    )


# Round 9 / B1: the lexical forms ("不足", "不到", ...) were double-negation
# checked with a fixed 3-character window, so a negator four characters away
# ("不得明显不足") was missed. The lexical forms now use the same clause-level
# scan as the bare direction words. The multi-threshold sentence is the guard
# against a too-wide scan: its second threshold must not see the first one's
# negator.
_LEXICAL_DOUBLE_NEGATION_CASES = [
    ("不得明显不足5000元", "低于5000元"),
    ("未曾明显不足5000元", "低于5000元"),
    ("不得不明显不足5000元", "低于5000元"),
]


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"), _LEXICAL_DOUBLE_NEGATION_CASES
)
def test_lexical_double_negation_uses_clause_scan(anchor_text, condition_text):
    assert _comparison_bounds(anchor_text) == set()
    assert _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert "ambiguous" in reason, reason


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"), _LEXICAL_DOUBLE_NEGATION_CASES
)
def test_rule_atom_rejects_lexical_double_negation(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)


def test_clause_scan_does_not_confuse_two_thresholds():
    phrase = "不低于5000元且不超过10000元"
    assert _comparison_bounds(phrase) == {
        ("upper", Decimal(5000)),
        ("lower", Decimal(10000)),
    }
    assert not _comparison_scope_is_ambiguous(phrase)


# Round 9 / B2: preventive verbs ("防止/避免/杜绝/切忌/谨防") state the negated
# comparison ("避免超过5000元" means <= 5000). They were not in the negation
# set, so the bare pattern read the anchor as a positive bound and accepted the
# reversed condition.
_PREVENTIVE_CASES = [
    ("应避免超过5000元", "lower"),
    ("报销金额应避免超过5000元", "lower"),
    ("应防止费用超过5000元", "lower"),
    ("杜绝超过5000元", "lower"),
    ("切忌超过5000元", "lower"),
    ("谨防超过5000元", "lower"),
    ("以免超过5000元", "lower"),
    ("以防费用超过5000元", "lower"),
    ("避免费用低于5000元", "upper"),
    ("防止低于5000元", "upper"),
    ("避免不足5000元", "upper"),
    ("应避免未达到5000元", "upper"),
]


@pytest.mark.parametrize(("phrase", "direction"), _PREVENTIVE_CASES)
def test_preventive_verb_states_the_negated_direction(phrase, direction):
    assert _comparison_bounds(phrase) == {(direction, Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(("phrase", "direction"), _PREVENTIVE_CASES)
def test_preventive_verb_rejects_the_reversed_condition(phrase, direction):
    reversed_text = "超过5000元" if direction == "lower" else "低于5000元"
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), reversed_text
    )
    assert "bounds" in reason and "claims" in reason, reason


def test_preventive_verb_accepts_the_matching_condition():
    anchor_text = "报销金额应避免超过5000元"
    assert (
        anchor_supports_text(
            _resolver(anchor_text), _anchor(anchor_text), "避免超过5000元"
        )
        == ""
    )


def test_preventive_verb_plus_negated_phrase_is_fail_closed():
    # "避免不超过5000元" is a double negation; the direction is not guessed.
    phrase = "避免不超过5000元"
    assert _comparison_scope_is_ambiguous(phrase)
    assert _comparison_bounds(phrase) == set()


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("报销金额应避免超过5000元", "超过5000元"),
        ("应防止费用超过5000元", "超过5000元"),
        ("杜绝超过5000元", "超过5000元"),
        ("谨防超过5000元", "超过5000元"),
        ("以免超过5000元", "超过5000元"),
        ("避免费用低于5000元", "低于5000元"),
    ],
)
def test_rule_atom_rejects_reversed_preventive_condition(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)


def test_rule_atom_accepts_grounded_preventive_condition(runtime, ctx):
    result = _define_rule(
        runtime, ctx, "报销金额应避免超过5000元", "避免超过5000元"
    )
    assert result.status.value == "ok", result.issues


# Round 9 / B3: "不含税", "未税", "未经批准" contain a negation character but
# do not negate the comparison. The clause scan used to reject the verbatim
# condition as ambiguous; the lexicalised prefixes are now blanked first.
_LEXICALISED_PREFIX_CASES = [
    ("不含税金额超过5000元", "upper"),
    ("未税金额超过5000元", "upper"),
    ("不含税金额不超过5000元", "lower"),
    ("未经批准不得低于5000元", "upper"),
]


@pytest.mark.parametrize(("phrase", "direction"), _LEXICALISED_PREFIX_CASES)
def test_lexicalised_negation_prefix_is_not_a_negator(phrase, direction):
    assert _comparison_bounds(phrase) == {(direction, Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize("phrase", [case[0] for case in _LEXICALISED_PREFIX_CASES])
def test_lexicalised_prefix_keeps_a_verbatim_condition_grounded(phrase):
    assert (
        anchor_supports_text(_resolver(phrase), _anchor(phrase), phrase) == ""
    )


def test_rule_atom_accepts_lexicalised_prefix(runtime, ctx):
    anchor_text = "不含税金额超过5000元"
    result = _define_rule(runtime, ctx, anchor_text, anchor_text)
    assert result.status.value == "ok", result.issues


def test_lexicalised_prefix_cannot_be_dropped_by_a_quote():
    # "含税金额" is a character substring of "不含税金额", but quoting it
    # drops the negation: the condition must not be grounded as a slice.
    anchor_text = "不含税金额超过5000元"
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), "含税金额超过5000元"
    )
    assert reason, (anchor_text, reason)
    assert "negation" in reason, reason


# Round 10 / B2: the preventive verb list was still closed and only scanned
# *before* the comparison. Two shapes escaped: a synonym missing from the list
# ("防范" for "防止") and a postposed verb ("费用超过5000元应避免"). Both read
# as a bare direction word and the atomic entry returned ``ok`` / ``issues=[]``
# for the reversed condition. The parser now consumes a wider synonym set, the
# fail-closed scope scan also matches preventive morphology outside the list,
# and it looks forward past the comparison (and past commas within the same
# sentence) for a preventive verb that survived.
_PREVENTIVE_SYNONYM_CASES = [
    ("应防范费用超过5000元", "lower"),
    ("应防范费用低于5000元", "upper"),
    ("应防范不足5000元", "upper"),
    ("应严防费用超过5000元", "lower"),
    ("应谨防费用超过5000元", "lower"),
    ("应预防费用超过5000元", "lower"),
    ("应提防费用超过5000元", "lower"),
    ("应防备费用超过5000元", "lower"),
    ("以避免费用超过5000元", "lower"),
    ("应阻止费用超过5000元", "lower"),
    ("应杜绝费用超过5000元", "lower"),
    ("应力戒费用超过5000元", "lower"),
]


@pytest.mark.parametrize(("phrase", "direction"), _PREVENTIVE_SYNONYM_CASES)
def test_preventive_synonym_states_the_negated_direction(phrase, direction):
    assert _comparison_bounds(phrase) == {(direction, Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(("phrase", "direction"), _PREVENTIVE_SYNONYM_CASES)
def test_preventive_synonym_rejects_the_reversed_condition(phrase, direction):
    reversed_text = "超过5000元" if direction == "lower" else "低于5000元"
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), reversed_text
    )
    assert reason, (phrase, reversed_text)


@pytest.mark.parametrize(
    "phrase",
    [
        # Synonyms outside the parsing list; the morphology rule catches them.
        "应根绝费用超过5000元",
        "应回避费用超过5000元",
        "应规避费用超过5000元",
        "应拒绝费用超过5000元",
        # Control/limit verbs scope the comparison but do not state which way
        # they invert it, so they must fail closed rather than guess a bound.
        "应控制费用超过5000元",
        "应限制费用超过5000元",
        "应限制费用低于5000元",
        "应约束费用超过5000元",
        "应根除费用超过5000元",
        # Attention verbs do not state a threshold at all.
        "应警惕费用超过5000元",
    ],
)
def test_unparsed_preventive_marker_is_fail_closed(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), "超过5000元"
    )
    assert "ambiguous" in reason, reason


_POSTPOSED_PREVENTIVE_CASES = [
    ("费用超过5000元应避免", "超过5000元"),
    ("超过5000元的费用应避免", "超过5000元"),
    ("费用超过5000元，应避免", "超过5000元"),
    ("费用超过5000元；应避免", "超过5000元"),
    ("费用超过5000元应防范", "超过5000元"),
    ("费用低于5000元应避免", "低于5000元"),
]


@pytest.mark.parametrize(("anchor_text", "condition_text"), _POSTPOSED_PREVENTIVE_CASES)
def test_postposed_preventive_verb_is_fail_closed(anchor_text, condition_text):
    assert _comparison_bounds(anchor_text) == set()
    assert _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert "ambiguous" in reason, reason
    # Even the verbatim anchor is refused: the direction is unknown.
    verbatim = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), anchor_text
    )
    assert "ambiguous" in verbatim, verbatim


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"), _POSTPOSED_PREVENTIVE_CASES
)
def test_rule_atom_rejects_postposed_preventive_verb(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)


@pytest.mark.parametrize(
    "phrase",
    [
        # "预防费用" / "防范成本" are noun compounds ("prevention cost"), not
        # a preventive verb scoping the comparison. Without a verbal context
        # they must not flip a plain "> 5000" anchor into a "<= 5000" bound.
        "预防费用超过5000元",
        "防范费用超过5000元",
        "防备费用超过5000元",
        "预防开支超过5000元",
        "防范费用低于5000元",
    ],
)
def test_preventive_noun_compound_is_fail_closed(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("应防范费用超过5000元", "超过5000元"),
        ("应防范费用低于5000元", "低于5000元"),
        ("应控制费用超过5000元", "超过5000元"),
        ("应根绝费用超过5000元", "超过5000元"),
    ],
)
def test_rule_atom_rejects_preventive_synonym_reversal(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (condition_text, codes)


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("应防范费用超过5000元", "应防范费用超过5000元"),
        ("应严防费用超过5000元", "应严防费用超过5000元"),
    ],
)
def test_rule_atom_accepts_the_grounded_preventive_synonym(
    runtime, ctx, anchor_text, condition_text
):
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "ok", result.issues


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # A purpose clause separated by a comma must not poison the comparison.
        ("为避免延误，费用超过5000元需审批", "超过5000元"),
        # Nouns that merely contain a preventive morpheme stay plain thresholds.
        ("消防费用超过5000元", "超过5000元"),
        ("费用超过5000元需经消防部门审批", "超过5000元"),
        # The lexicalised idiom is blanked, not read as a preventive verb.
        ("不可避免超过5000元", "超过5000元"),
        ("超过5000元，需审批", "超过5000元"),
    ],
)
def test_preventive_scan_does_not_over_reject(anchor_text, condition_text):
    assert not _comparison_scope_is_ambiguous(anchor_text), anchor_text
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert reason == "", (anchor_text, reason)


# Round 11 / B2: preventive verbs at the *start of a clause* escaped the
# fail-closed scan. The round 10 morphology rule required a leading Han
# character ("[汉][防避忌…]"), so "避开超过5000元" -- with no "应"/"须" in
# front -- matched nothing, read as a bare "upper" bound, and the atomic entry
# accepted the reversed condition "超过5000元" with ok/issues=[]. The explicit
# verb list now parses the common clause-initial synonyms, and the morphology
# rule also matches a preventive morpheme at a clause start. Noun compounds
# that merely begin with such a morpheme ("防火费用", "避险成本") stay plain
# thresholds instead of being rejected as ambiguous.
_CLAUSE_INITIAL_PREVENTIVE_CASES = [
    ("避开超过5000元", "lower"),
    ("避让超过5000元", "lower"),
    ("戒掉超过5000元", "lower"),
    ("戒绝超过5000元", "lower"),
    ("躲避超过5000元", "lower"),
    ("躲开超过5000元", "lower"),
    ("避掉超过5000元", "lower"),
    ("避开费用超过5000元", "lower"),
    ("避开低于5000元", "upper"),
    ("避让低于5000元", "upper"),
    ("戒掉不足5000元", "upper"),
    ("戒绝未达到5000元", "upper"),
    # A modal before the clause-initial verb still parses the same way.
    ("应避开超过5000元", "lower"),
    ("须避让高于5000元", "lower"),
]


@pytest.mark.parametrize(("phrase", "direction"), _CLAUSE_INITIAL_PREVENTIVE_CASES)
def test_clause_initial_preventive_verb_states_the_negated_direction(
    phrase, direction
):
    assert _comparison_bounds(phrase) == {(direction, Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(("phrase", "direction"), _CLAUSE_INITIAL_PREVENTIVE_CASES)
def test_clause_initial_preventive_verb_rejects_the_reversed_condition(
    phrase, direction
):
    reversed_text = "超过5000元" if direction == "lower" else "低于5000元"
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), reversed_text
    )
    assert reason, (phrase, reversed_text)
    assert "bounds" in reason and "claims" in reason, reason


@pytest.mark.parametrize(("phrase", "direction"), _CLAUSE_INITIAL_PREVENTIVE_CASES)
def test_rule_atom_rejects_clause_initial_preventive_reversal(
    runtime, ctx, phrase, direction
):
    reversed_text = "超过5000元" if direction == "lower" else "低于5000元"
    result = _define_rule(runtime, ctx, phrase, reversed_text)
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (phrase, codes)


@pytest.mark.parametrize(
    "anchor_text",
    [
        "避开超过5000元",
        "避让超过5000元",
        "戒掉超过5000元",
        "应避开费用超过5000元",
    ],
)
def test_clause_initial_preventive_verb_keeps_a_grounded_condition(
    runtime, ctx, anchor_text
):
    assert (
        anchor_supports_text(_resolver(anchor_text), _anchor(anchor_text), anchor_text)
        == ""
    )
    result = _define_rule(runtime, ctx, anchor_text, anchor_text)
    assert result.status.value == "ok", result.issues


_PREVENTIVE_OPEN_VOCABULARY_CASES = [
    # Synonyms outside the parsing list: the clause-start morphology rule must
    # fail them closed instead of reading the bare direction word.
    "阻断超过5000元",
    "阻挠超过5000元",
    "阻挡超过5000元",
    "遏阻超过5000元",
]


@pytest.mark.parametrize("phrase", _PREVENTIVE_OPEN_VOCABULARY_CASES)
def test_unparsed_clause_initial_preventive_verb_is_fail_closed(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), "超过5000元"
    )
    assert "ambiguous" in reason, reason


@pytest.mark.parametrize("phrase", _PREVENTIVE_OPEN_VOCABULARY_CASES)
def test_rule_atom_rejects_unparsed_clause_initial_preventive_verb(
    runtime, ctx, phrase
):
    result = _define_rule(runtime, ctx, phrase, "超过5000元")
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (phrase, codes)


@pytest.mark.parametrize(
    "phrase",
    [
        # The postposed form of a clause-initial synonym is not consumed; the
        # direction stays unreadable rather than being guessed.
        "费用超过5000元应避开",
        "费用超过5000元应避让",
        "费用超过5000元应戒掉",
        # Double negation under a clause-initial verb.
        "避开不超过5000元",
        "避让不低于5000元",
    ],
)
def test_clause_initial_preventive_verb_fails_closed_when_unconsumed(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # Noun compounds that begin with a preventive morpheme are not verbs
        # scoping the comparison; they must stay plain thresholds.
        ("防火费用超过5000元", "超过5000元"),
        ("防灾支出超过5000元", "超过5000元"),
        ("避险成本超过5000元", "超过5000元"),
        ("戒烟费用超过5000元", "超过5000元"),
        ("阻抗费用超过5000元", "超过5000元"),
        # "绝对" is an emphatic adverb, not a preventive verb.
        ("绝对超过5000元", "超过5000元"),
        # A purpose clause before the comma must not poison the comparison.
        ("避开风险，费用超过5000元需审批", "超过5000元"),
    ],
)
def test_clause_initial_preventive_scan_does_not_over_reject(
    runtime, ctx, anchor_text, condition_text
):
    assert not _comparison_scope_is_ambiguous(anchor_text), anchor_text
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert reason == "", (anchor_text, reason)
    result = _define_rule(runtime, ctx, anchor_text, condition_text)
    assert result.status.value == "ok", result.issues


# Round 11 / B2 (double prevention): two preventive verbs in one scope invert
# the comparison twice ("避免避开超过5000元" = do not avoid exceeding, i.e.
# >= 5000). Reading only the first verb would silently reverse the direction,
# so the bound is left unconsumed and the ambiguity scan fails it closed.
_DOUBLE_PREVENTIVE_CASES = [
    "避免避开超过5000元",
    "避开避免超过5000元",
    "防止避开超过5000元",
    "杜绝避开低于5000元",
]


@pytest.mark.parametrize("phrase", _DOUBLE_PREVENTIVE_CASES)
def test_double_preventive_scope_is_fail_closed(phrase):
    assert _comparison_bounds(phrase) == set()
    assert _comparison_scope_is_ambiguous(phrase)
    reversed_text = "超过5000元" if "超过" in phrase else "低于5000元"
    reason = anchor_supports_text(
        _resolver(phrase), _anchor(phrase), reversed_text
    )
    assert "ambiguous" in reason, reason
    verbatim = anchor_supports_text(_resolver(phrase), _anchor(phrase), phrase)
    assert "ambiguous" in verbatim, verbatim


@pytest.mark.parametrize("phrase", _DOUBLE_PREVENTIVE_CASES)
def test_rule_atom_rejects_double_preventive_scope(runtime, ctx, phrase):
    result = _define_rule(runtime, ctx, phrase, "超过5000元")
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes, (phrase, codes)


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # A second preventive-looking word that is really a noun compound does
        # not invert anything: "prevention costs" stays a plain threshold.
        ("避免防范费用超过5000元", "超过5000元"),
        ("避免预防费用超过5000元", "超过5000元"),
        ("避免消防费用超过5000元", "超过5000元"),
    ],
)
def test_double_preventive_does_not_over_reject_noun_compounds(
    anchor_text, condition_text
):
    assert _comparison_bounds(anchor_text) == {("lower", Decimal(5000))}
    assert not _comparison_scope_is_ambiguous(anchor_text)
    reason = anchor_supports_text(
        _resolver(anchor_text), _anchor(anchor_text), condition_text
    )
    assert "bounds" in reason and "claims" in reason, reason
