import math
import pandas as pd



# Each emotion is represented as a fixed point in 3D space:
# (Valence, Arousal, Sociality)
# Not hard rules can be changed. just the map of emotional centers


EMOTION_ANCHORS = {
    "Love/Ecstasy":         ( 1.0, 0.6,  1.0),
    "Excitement/Elation":   ( 0.9, 0.8, -0.5),
    "Anger/Rage":           (-0.7, 1.0,  0.7),
    "Fear/Terror":          (-0.8, 0.9, -0.9),
    "Distress/Anxiety":     (-0.6, 0.7,  0.0),
    "Disgust/Aversion":     (-0.5, 0.7, -0.9),
    "Sadness/Grief":        (-0.7, 0.3, -0.2),
    "Serenity/Contentment": ( 0.8, 0.1,  0.5),
    "Calmness/Apathy":      ( 0.0, 0.0,  0.0),
    "Relaxation":           ( 0.3, 0.1,  0.2),
    "Boredom/Dullness":     (-0.3, 0.1, -0.3),
    "Interest/Ambivalence": ( 0.0, 0.4,  0.0),
}



# Radial Basis Function (Gaussian)

# Converts a distance into an activation strength.

# distance == 0  -> activation == 1.0
# farther away   -> activation smoothly decays toward 0

# sigma controls "emotion spread":
#   smaller sigma -> sharper emotions
#   larger sigma   -> more blending
#   sigma represents what is essentially a gravity well.

def gaussian_rbf(distance_from_anchor, sigma=0.35):
    """
    Computes Gaussian RBF activation for a given distance.
    """
    return math.exp(
        -(distance_from_anchor ** 2) / (2 * sigma ** 2)
    )


# Euclidean distance in VAS space
#
# measures how far the agent's current emotional state is from a given emotion anchor.

def euclidean_distance(agent_vas_point, emotion_anchor_point):
    """
    Computes Euclidean distance between two VAS vectors.
    """

    squared_differences = []

    # Pair each axis (V, A, S) between agent and anchor
    for agent_value, anchor_value in zip(agent_vas_point, emotion_anchor_point):
        difference = agent_value - anchor_value
        squared_differences.append(difference ** 2)

    # Distance = sqrt(sum of squared axis differences)
    return math.sqrt(sum(squared_differences))



# Core RBF emotion distribution
# Output example:
# {
#   "Fear/Terror": 0.42,
#   "Distress/Anxiety": 0.31,
# }


def map_vas_rbf_distribution(
    valence,
    arousal,
    sociality,
    sigma=0.35
):
    """
    Maps a VAS point to a normalized emotion probability distribution.
    """

    agent_vas_point = (valence, arousal, sociality)
    emotion_activations = {}

    # Compute RBF activation for each emotion anchor
    for emotion_label, anchor_point in EMOTION_ANCHORS.items():

        distance_to_anchor = euclidean_distance(
            agent_vas_point,
            anchor_point
        )

        activation_strength = gaussian_rbf(
            distance_to_anchor,
            sigma
        )

        emotion_activations[emotion_label] = activation_strength

    # Normalize activations so they sum to 1.0
    total_activation = sum(emotion_activations.values())

    for emotion_label in emotion_activations:
        emotion_activations[emotion_label] /= total_activation

    return emotion_activations



# replacement for original IF/ELSE mapper.
# Keeps the same function name and signature.
# Returns the strongest emotion label.


def map_vas_to_label(valence, arousal, sociality):
    """
    Returns the dominant emotion label using RBF competition.
    """

    emotion_distribution = map_vas_rbf_distribution(
        valence,
        arousal,
        sociality
    )

    # Choose the emotion with the highest activation
    return max(
        emotion_distribution,
        key=emotion_distribution.get
    )



# Test. Unchanged Logically

def main():
    """Runs validation tests against known VAS cases."""

    test_cases = [
        {"V": 1.0,  "A": 0.6, "S": 1.0,   "Name": "Love (Anchor)",        "Expected": "Love/Ecstasy"},
        {"V": -0.7, "A": 1.0, "S": 0.7,   "Name": "Anger (Anchor)",       "Expected": "Anger/Rage"},
        {"V": -0.5, "A": 0.7, "S": -0.9,  "Name": "Disgust (Anchor)",     "Expected": "Disgust/Aversion"},
        {"V": -0.18,"A": 0.42,"S": -0.028,"Name": "Annoyance Case",       "Expected": "Interest/Ambivalence"},
        {"V": 0.8,  "A": 0.1, "S": 0.5,   "Name": "Serenity",             "Expected": "Serenity/Contentment"},
        {"V": 0.0,  "A": 0.0, "S": 0.0,   "Name": "Neutral Calm",         "Expected": "Calmness/Apathy"},
        {"V": -0.9, "A": 0.9, "S": -0.9,  "Name": "Terror/Fear",          "Expected": "Fear/Terror"},
        {"V": -0.8, "A": 0.3, "S": -0.2,  "Name": "Grief/Sadness",        "Expected": "Sadness/Grief"},
    ]

    results = []

    print("--- Running VAS Emotion Mapping Tests ---\n")

    for case in test_cases:
        valence = case["V"]
        arousal = case["A"]
        sociality = case["S"]

        predicted_label = map_vas_to_label(
            valence,
            arousal,
            sociality
        )

        results.append({
            "Test Case": case["Name"],
            "V": valence,
            "A": arousal,
            "S": sociality,
            "Expected Label": case["Expected"],
            "Actual Label": predicted_label,
            "Status": "PASS" if predicted_label == case["Expected"]
                      else f"FAIL (Got: {predicted_label})"
        })

    df = pd.DataFrame(results)

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)

    print(df.to_string(index=False))

    failed_tests = df["Status"].str.startswith("FAIL").sum()

    print("\n--- Test Summary ---")
    print(f"Total Tests Run: {len(df)}")
    print(f"Total Tests Passed: {len(df) - failed_tests}")
    print(f"Total Tests Failed: {failed_tests}")
    print(f"Result: {'SUCCESS' if failed_tests == 0 else 'FAILURE'}")


if __name__ == "__main__":
    main()
