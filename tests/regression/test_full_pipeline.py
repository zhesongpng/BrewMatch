"""Full pipeline integration test for BrewMatch.

Exercises the complete pipeline from bean profile construction through
retrieval (mocked), taste prediction, recipe optimization, and diagnosis.
Validates that data models flow correctly between every stage and that
each stage produces valid, range-appropriate outputs.

Red team finding M2-L12: No integration test across full pipeline.
"""

import numpy as np
import pytest

from src.bean_extractor.extractor import create_manual_profile
from src.data_models import (
    BeanProfile,
    BrewMethod,
    FLAVOR_CLUSTERS,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)
from src.diagnosis.engine import DiagnosisEngine, DiagnosisResult, DiagnosisSuggestion
from src.recipe_optimizer.optimizer import OptimizationResult, RecipeOptimizer
from src.recipe_retriever.retriever import (
    RankedRecipe,
    RecipeRetriever,
    RetrievalResult,
    compute_rerank_score,
)
from src.taste_predictor.encoder import encode_features
from src.taste_predictor.model import PredictionResult, TastePredictor


# ---------------------------------------------------------------------------
# Helpers: deterministic synthetic training data
# ---------------------------------------------------------------------------

_SEED = 42
_RNG = np.random.RandomState(_SEED)
_N_TRAIN = 80
_N_VAL = 20


def _make_synthetic_bean(index: int) -> BeanProfile:
    """Create a deterministic bean profile for training sample *index*."""
    countries = ["Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala"]
    processes = [Process.WASHED, Process.NATURAL, Process.HONEY]
    roasts = [RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT, RoastLevel.MEDIUM]

    rng = np.random.RandomState(_SEED + index)
    return BeanProfile(
        origin_country=countries[index % len(countries)],
        process=processes[index % len(processes)],
        roast_level=roasts[index % len(roasts)],
        flavor_clusters=[
            FLAVOR_CLUSTERS[index % len(FLAVOR_CLUSTERS)],
            FLAVOR_CLUSTERS[(index + 3) % len(FLAVOR_CLUSTERS)],
        ],
        source_text="synthetic training bean",
    )


def _make_synthetic_recipe(index: int) -> Recipe:
    """Create a deterministic recipe for training sample *index*."""
    rng = np.random.RandomState(_SEED + index + 1000)
    dose_g = 12.0 + rng.uniform(0, 10)  # 12-22
    ratio = 14.0 + rng.uniform(0, 4)    # 14-18
    water_total_g = round(dose_g * ratio, 1)
    # Clamp to Recipe validation bounds
    water_total_g = max(180.0, min(600.0, water_total_g))
    ratio = round(water_total_g / dose_g, 2)
    ratio = max(14.0, min(18.0, ratio))
    water_total_g = round(dose_g * ratio, 1)

    return Recipe(
        recipe_id=f"synth-recipe-{index:04d}",
        source="synthetic",
        method=BrewMethod.V60,
        dose_g=round(dose_g, 1),
        water_total_g=water_total_g,
        ratio=ratio,
        grind_setting=int(1 + rng.randint(0, 10)),
        water_temp_c=round(85.0 + rng.uniform(0, 15), 1),
        bloom_time_s=30,
        total_time_s=180,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=round(water_total_g * 0.3, 1)),
            PourStep(
                step=2,
                time_offset_s=30,
                water_g=round(water_total_g * 0.35, 1),
            ),
            PourStep(
                step=3,
                time_offset_s=80,
                water_g=round(water_total_g * 0.35, 1),
            ),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT, RoastLevel.MEDIUM],
            origins=["Ethiopia", "Colombia"],
            processes=[Process.WASHED, Process.NATURAL],
            flavor_profiles=["Floral", "Citrus", "Berry"],
        ),
        instructions="Synthetic recipe for training data.",
    )


def _generate_training_data():
    """Generate deterministic feature arrays and target ratings."""
    X_rows = []
    y_ratings = []

    for i in range(_N_TRAIN + _N_VAL):
        bean = _make_synthetic_bean(i)
        recipe = _make_synthetic_recipe(i)
        features = encode_features(bean, recipe)

        # Deterministic rating: combination of features plus small noise
        rng = np.random.RandomState(_SEED + i + 2000)
        # Base rating from a few feature columns, shifted to [3, 9] range
        raw = (
            features[6] * 0.5       # roast ordinal
            + features[23] * 0.1    # dose
            + features[26] * 0.02   # water temp
            + rng.normal(0, 0.3)
        )
        rating = float(np.clip(raw, 3.0, 9.0))

        X_rows.append(features)
        y_ratings.append(rating)

    X = np.array(X_rows)
    y = np.array(y_ratings)

    return X[:_N_TRAIN], y[:_N_TRAIN], X[_N_TRAIN:], y[_N_TRAIN:]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trained_predictor():
    """Module-scoped TastePredictor trained on synthetic data."""
    predictor = TastePredictor()
    X_train, y_train, X_val, y_val = _generate_training_data()
    predictor.train(X_train, y_train, X_val, y_val)
    assert predictor.is_trained
    return predictor


@pytest.fixture()
def test_bean():
    """A bean profile representing a light-roast Ethiopian for pipeline testing."""
    result = create_manual_profile(
        origin_country="Ethiopia",
        process="washed",
        roast_level="light",
        flavor_clusters=["Floral", "Citrus"],
        origin_region="Yirgacheffe",
        variety="Gesha",
        altitude_min_m=1800,
        altitude_max_m=2200,
    )
    assert result.confidence == 1.0
    assert result.used_manual_entry is True
    return result.bean_profile


@pytest.fixture()
def test_recipes():
    """A small in-memory recipe database for retrieval testing."""
    recipes = [
        Recipe(
            recipe_id="pipeline-test-eth-v60",
            source="Test Pipeline",
            method=BrewMethod.V60,
            dose_g=15.0,
            water_total_g=250.0,
            ratio=16.67,
            grind_setting=5,
            water_temp_c=93.0,
            bloom_time_s=45,
            total_time_s=210,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=50.0),
                PourStep(step=2, time_offset_s=45, water_g=100.0),
                PourStep(step=3, time_offset_s=90, water_g=100.0),
            ],
            suitable_for=SuitableFor(
                roast_levels=[RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT],
                origins=["Ethiopia", "Kenya"],
                processes=[Process.WASHED],
                flavor_profiles=["Floral", "Citrus", "Berry"],
            ),
            instructions="Bloom with 50g, then two equal pours.",
        ),
        Recipe(
            recipe_id="pipeline-test-col-kalita",
            source="Test Pipeline",
            method=BrewMethod.KALITA_WAVE,
            dose_g=16.0,
            water_total_g=256.0,
            ratio=16.0,
            grind_setting=4,
            water_temp_c=92.0,
            bloom_time_s=30,
            total_time_s=195,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=30, water_g=100.0),
                PourStep(step=3, time_offset_s=75, water_g=96.0),
            ],
            suitable_for=SuitableFor(
                roast_levels=[RoastLevel.LIGHT, RoastLevel.MEDIUM],
                origins=["Colombia", "Ethiopia"],
                processes=[Process.WASHED, Process.NATURAL],
                flavor_profiles=["Chocolate", "Nutty", "Balanced"],
            ),
            instructions="Kalita Wave recipe for balanced extraction.",
        ),
        Recipe(
            recipe_id="pipeline-test-dark-origami",
            source="Test Pipeline",
            method=BrewMethod.ORIGAMI,
            dose_g=18.0,
            water_total_g=288.0,
            ratio=16.0,
            grind_setting=6,
            water_temp_c=90.0,
            bloom_time_s=40,
            total_time_s=240,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=40, water_g=114.0),
                PourStep(step=3, time_offset_s=100, water_g=114.0),
            ],
            suitable_for=SuitableFor(
                roast_levels=[RoastLevel.MEDIUM_DARK, RoastLevel.DARK],
                origins=["Brazil", "Indonesia"],
                processes=[Process.NATURAL, Process.WET_HULLED],
                flavor_profiles=["Chocolate", "Roasted", "Spice"],
            ),
            instructions="Origami recipe for dark roasts.",
        ),
    ]
    return recipes


# ---------------------------------------------------------------------------
# Test: full pipeline
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_full_pipeline_end_to_end(trained_predictor, test_bean, test_recipes):
    """Exercise the full BrewMatch pipeline from bean to diagnosis.

    Stages:
        1. Bean profile constructed via manual entry (skips LLM extraction).
        2. Recipes scored and filtered via reranking signals.
        3. Best recipe predicted with TastePredictor.
        4. Recipe optimized via RecipeOptimizer.
        5. Diagnosis engine runs perturb-and-score analysis.
        6. Every output is validated against its data model constraints.
    """
    bean = test_bean

    # ---- Stage 1: Bean profile validates ----
    assert isinstance(bean, BeanProfile)
    assert bean.origin_country == "Ethiopia"
    assert bean.process == Process.WASHED
    assert bean.roast_level == RoastLevel.LIGHT
    assert len(bean.flavor_clusters) >= 1
    for fc in bean.flavor_clusters:
        assert fc in FLAVOR_CLUSTERS

    # ---- Stage 2: Recipe retrieval (simulated via reranking) ----
    # Since RecipeRetriever requires ChromaDB/sentence-transformers for
    # full indexing, we use the reranking function directly to score and
    # rank the in-memory recipes against the bean profile.
    scored_recipes = []
    for recipe in test_recipes:
        signals = compute_rerank_score(recipe, bean)
        scored_recipes.append((recipe, signals["combined"], signals))

    scored_recipes.sort(key=lambda x: x[1], reverse=True)

    # Assert: at least one recipe matches the bean's roast/method
    assert len(scored_recipes) >= 1, "Reranking returned zero recipes"

    # The top recipe should be the Ethiopian V60 (matching origin, roast,
    # process, and flavor clusters).
    top_recipe = scored_recipes[0][0]
    top_signals = scored_recipes[0][2]

    # Assert: reranking signals are valid floats in [0, 1]
    for signal_name, signal_value in top_signals.items():
        assert isinstance(signal_value, float), (
            f"Signal {signal_name} is {type(signal_value)}, expected float"
        )
        if signal_name != "combined":
            assert 0.0 <= signal_value <= 1.0, (
                f"Signal {signal_name}={signal_value} outside [0, 1]"
            )

    # Assert: process_match is 1.0 for the V60 recipe (bean is washed,
    # recipe suitable_for includes washed).
    assert top_signals["process_match"] == 1.0, (
        "Top recipe should match bean process (washed)"
    )

    # Build a RetrievalResult to simulate retriever output
    ranked = [
        RankedRecipe(
            recipe=r,
            rank=i + 1,
            score=round(s, 4),
            relevance_signals={k: round(v, 4) for k, v in sig.items()},
        )
        for i, (r, s, sig) in enumerate(scored_recipes)
    ]
    retrieval_result = RetrievalResult(
        recipes=ranked,
        total_candidates=len(test_recipes),
        query_bean_id=None,
    )

    # Assert: RetrievalResult structure is valid
    assert retrieval_result.total_candidates == len(test_recipes)
    assert len(retrieval_result.recipes) == len(test_recipes)
    assert retrieval_result.recipes[0].rank == 1
    assert retrieval_result.recipes[0].score >= 0.0

    # ---- Stage 3: Taste prediction on the top recipe ----
    base_recipe = ranked[0].recipe
    prediction = trained_predictor.predict(bean, base_recipe)

    # Assert: PredictionResult structure and rating range
    assert isinstance(prediction, PredictionResult)
    assert 1.0 <= prediction.predicted_rating <= 10.0, (
        f"Predicted rating {prediction.predicted_rating} outside [1, 10]"
    )
    assert len(prediction.confidence_interval) == 2
    ci_lo, ci_hi = prediction.confidence_interval
    assert ci_lo <= ci_hi, (
        f"Confidence interval inverted: [{ci_lo}, {ci_hi}]"
    )
    assert 1.0 <= ci_lo <= 10.0
    assert 1.0 <= ci_hi <= 10.0
    assert isinstance(prediction.user_bias, float)
    assert isinstance(prediction.base_prediction, float)
    assert isinstance(prediction.feature_importance, dict)
    assert len(prediction.feature_importance) > 0

    # ---- Stage 4: Feature encoding consistency check ----
    features = trained_predictor.encode_features(bean, base_recipe)
    assert isinstance(features, np.ndarray)
    assert features.shape == (45,), f"Expected 45 features, got {features.shape}"
    assert np.isfinite(features).all(), "Feature array contains NaN or Inf"

    # ---- Stage 5: Recipe optimization ----
    optimizer = RecipeOptimizer(
        predictor=trained_predictor,
        n_trials=10,  # small budget for test speed
        seed=_SEED,
    )
    opt_result = optimizer.optimize(bean, base_recipe)

    # Assert: OptimizationResult structure
    assert isinstance(opt_result, OptimizationResult)
    assert isinstance(opt_result.optimized_recipe, Recipe)
    assert 1.0 <= opt_result.predicted_score <= 10.0, (
        f"Optimized predicted score {opt_result.predicted_score} outside [1, 10]"
    )
    assert opt_result.improvement >= 0.0, (
        f"Optimization produced negative improvement: {opt_result.improvement}"
    )
    assert opt_result.n_trials > 0
    assert isinstance(opt_result.parameter_changes, dict)
    assert isinstance(opt_result.constraint_violations, list)
    assert isinstance(opt_result.convergence_reached, bool)

    # Assert: optimized recipe still passes data model validation
    optimized = opt_result.optimized_recipe
    assert 12.0 <= optimized.dose_g <= 35.0
    assert 180.0 <= optimized.water_total_g <= 600.0
    assert 14.0 <= optimized.ratio <= 18.0
    assert 1 <= optimized.grind_setting <= 10
    assert 85.0 <= optimized.water_temp_c <= 100.0
    assert 120 <= optimized.total_time_s <= 360
    assert 1 <= len(optimized.pours) <= 6

    # ---- Stage 6: Diagnosis engine ----
    diagnosis_engine = DiagnosisEngine(predictor=trained_predictor)
    diagnosis_result = diagnosis_engine.diagnose(
        bean_profile=bean,
        recipe=base_recipe,
        flags=["too_sour", "too_weak"],
    )

    # Assert: DiagnosisResult structure
    assert isinstance(diagnosis_result, DiagnosisResult)
    assert diagnosis_result.issue_flags == ["too_sour", "too_weak"]
    assert isinstance(diagnosis_result.suggestions, list)
    assert len(diagnosis_result.suggestions) > 0, (
        "Diagnosis returned zero suggestions for reported flags"
    )
    assert isinstance(diagnosis_result.overall_assessment, str)
    assert len(diagnosis_result.overall_assessment) > 0

    # Assert: base_score is in valid range
    assert 1.0 <= diagnosis_result.base_score <= 10.0, (
        f"Diagnosis base_score {diagnosis_result.base_score} outside [1, 10]"
    )

    # Assert: best_case_score >= base_score
    assert diagnosis_result.best_case_score >= diagnosis_result.base_score, (
        f"best_case_score {diagnosis_result.best_case_score} < "
        f"base_score {diagnosis_result.base_score}"
    )

    # Assert: predicted_improvement is non-negative
    assert diagnosis_result.predicted_improvement >= 0.0, (
        f"predicted_improvement {diagnosis_result.predicted_improvement} is negative"
    )

    # Assert: each suggestion is valid
    for suggestion in diagnosis_result.suggestions:
        assert isinstance(suggestion, DiagnosisSuggestion)
        assert suggestion.parameter in (
            "grind_setting", "water_temp_c", "dose_g", "ratio"
        ), f"Unexpected parameter: {suggestion.parameter}"
        assert 0.0 <= suggestion.confidence <= 1.0, (
            f"Suggestion confidence {suggestion.confidence} outside [0, 1]"
        )
        assert isinstance(suggestion.reason, str)
        assert len(suggestion.reason) > 0, "Suggestion has empty reason"
        assert isinstance(suggestion.score_delta, float)

    # ---- Cross-stage consistency checks ----

    # The prediction's predicted_rating should match diagnosis base_score
    # (both call predict() on the same bean+recipe combination)
    assert abs(prediction.predicted_rating - diagnosis_result.base_score) < 0.01, (
        f"Prediction rating ({prediction.predicted_rating}) disagrees with "
        f"diagnosis base_score ({diagnosis_result.base_score})"
    )

    # Optimized recipe score should be >= base prediction
    assert opt_result.predicted_score >= prediction.predicted_rating or opt_result.improvement == 0.0, (
        f"Optimized score ({opt_result.predicted_score}) < "
        f"base prediction ({prediction.predicted_rating}) "
        f"but improvement is not zero"
    )


@pytest.mark.regression
def test_full_pipeline_feature_encoding_across_stages(
    trained_predictor, test_bean, test_recipes
):
    """Verify feature encoding is consistent when the same bean+recipe
    combination is encoded by the predictor, optimizer, and diagnosis engine.

    This catches a common failure mode where different pipeline stages
    use incompatible feature shapes.
    """
    bean = test_bean
    recipe = test_recipes[0]  # Ethiopian V60

    # Encode via the predictor's public API
    features_predictor = trained_predictor.encode_features(bean, recipe)

    # Encode via the module-level function
    features_direct = encode_features(bean, recipe)

    # Must be identical
    assert np.allclose(features_predictor, features_direct), (
        "Predictor.encode_features() disagrees with encode_features()"
    )

    # Shape must be 45
    assert features_predictor.shape == (45,)
    assert features_direct.shape == (45,)

    # Prediction must work on the encoded features
    assert trained_predictor.is_trained
    prediction = trained_predictor.predict(bean, recipe)
    assert 1.0 <= prediction.predicted_rating <= 10.0

    # Batch prediction on the same features must agree
    batch_scores = trained_predictor.predict_batch(
        features_predictor.reshape(1, -1)
    )
    assert len(batch_scores) == 1
    # Batch prediction may differ slightly from single predict due to
    # user_bias (predict applies bias, predict_batch does too when no user_ids)
    assert abs(float(batch_scores[0]) - prediction.predicted_rating) < 0.01, (
        f"Batch prediction ({batch_scores[0]}) disagrees with "
        f"single prediction ({prediction.predicted_rating})"
    )


@pytest.mark.regression
def test_full_pipeline_diagnosis_with_all_flags(
    trained_predictor, test_bean, test_recipes
):
    """Run diagnosis with every valid directional flag and verify all
    suggestions have valid confidence, reason, and parameter values."""
    bean = test_bean
    recipe = test_recipes[0]

    engine = DiagnosisEngine(predictor=trained_predictor)
    all_flags = ["too_sour", "too_bitter", "too_weak", "too_harsh", "astringent"]

    result = engine.diagnose(bean, recipe, flags=all_flags)

    assert result.issue_flags == all_flags
    assert len(result.suggestions) == 4, (
        f"Expected 4 suggestions (one per parameter), got {len(result.suggestions)}"
    )

    for suggestion in result.suggestions:
        assert 0.0 <= suggestion.confidence <= 1.0
        assert suggestion.parameter in (
            "grind_setting", "water_temp_c", "dose_g", "ratio"
        )
        # Every suggestion should have a non-empty explanation
        assert len(suggestion.reason) > 20, (
            f"Reason for {suggestion.parameter} is suspiciously short: "
            f"'{suggestion.reason}'"
        )

    # Suggestions must be sorted by score_delta descending
    deltas = [s.score_delta for s in result.suggestions]
    assert deltas == sorted(deltas, reverse=True), (
        f"Suggestions not sorted by score_delta: {deltas}"
    )


@pytest.mark.regression
def test_full_pipeline_optimizer_preserves_recipe_structure(
    trained_predictor, test_bean, test_recipes
):
    """Verify that the optimizer preserves the pour schedule structure
    and recipe metadata, only changing tunable parameters."""
    bean = test_bean
    recipe = test_recipes[0]

    optimizer = RecipeOptimizer(
        predictor=trained_predictor,
        n_trials=10,
        seed=_SEED,
    )
    result = optimizer.optimize(bean, recipe)

    optimized = result.optimized_recipe

    # Preserved fields
    assert optimized.recipe_id == recipe.recipe_id
    assert optimized.source == recipe.source
    assert optimized.method == recipe.method
    assert optimized.bloom_time_s == recipe.bloom_time_s
    assert optimized.total_time_s == recipe.total_time_s
    assert optimized.suitable_for == recipe.suitable_for
    assert optimized.instructions == recipe.instructions
    assert optimized.source_url == recipe.source_url

    # Pour count preserved
    assert len(optimized.pours) == len(recipe.pours)

    # Pour steps and timing preserved
    for orig, opt in zip(recipe.pours, optimized.pours):
        assert opt.step == orig.step
        assert opt.time_offset_s == orig.time_offset_s

    # Optimized recipe passes full validation (already enforced by Recipe
    # __post_init__, but re-verify the invariants explicitly)
    assert 12.0 <= optimized.dose_g <= 35.0
    assert 180.0 <= optimized.water_total_g <= 600.0
    assert 14.0 <= optimized.ratio <= 18.0
    assert 1 <= optimized.grind_setting <= 10
    assert 85.0 <= optimized.water_temp_c <= 100.0

    # water_total_g must be within 5% of pour sum
    pour_sum = sum(p.water_g for p in optimized.pours)
    assert abs(pour_sum - optimized.water_total_g) <= optimized.water_total_g * 0.05, (
        f"Pour sum {pour_sum} not within 5% of water_total_g {optimized.water_total_g}"
    )

    # ratio must be water_total_g / dose_g within 0.1
    expected_ratio = optimized.water_total_g / optimized.dose_g
    assert abs(optimized.ratio - expected_ratio) <= 0.1, (
        f"ratio {optimized.ratio} != water/dose {expected_ratio:.2f}"
    )
