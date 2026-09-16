"""
Recommendation Generator (stub).

Future milestone: will generate actionable but safe recommendations
based on the diagnosis.

Safety policy — the recommender will NEVER suggest actions that
automatically modify the system.  All recommendations are advisory.
"""


class Recommender:
    """Generates safe, actionable recommendations from a diagnosis.

    Not yet implemented — placeholder for a future milestone.
    """

    def recommend(self, diagnosis: dict) -> list:
        """Generate recommendations from a diagnosis result.

        Args:
            diagnosis: Output from the DiagnosisEngine.

        Returns:
            A list of recommendation strings.

        Raises:
            NotImplementedError: Always — not yet implemented.
        """
        raise NotImplementedError(
            "Recommender is not yet implemented (future milestone)."
        )
