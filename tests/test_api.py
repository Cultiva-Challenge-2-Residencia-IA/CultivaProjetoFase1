import unittest

from src.api.app import NutritionAPI


class ApiTests(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        app = NutritionAPI()
        payload = app.health()

        self.assertEqual(payload["status"], "ok")

    def test_ask_endpoint_returns_answer_schema(self) -> None:
        app = NutritionAPI()
        payload = app.ask({"question": "Como melhorar a hidratação no dia a dia?"})

        self.assertIn("answer", payload)
        self.assertIn("claims", payload)
        self.assertIn("sources", payload)
        self.assertIn("confianca", payload)
        self.assertIn("recusou", payload)
        self.assertIn("trace_id", payload)

    def test_scope_requests_are_refused(self) -> None:
        app = NutritionAPI()
        payload = app.ask({"question": "Crie uma dieta de 1.200 kcal para emagrecer em 3 semanas."})

        self.assertTrue(payload["recusou"])
        self.assertIn("prescrição", payload["answer"].lower())

    def test_feedback_endpoint_accepts_feedback(self) -> None:
        app = NutritionAPI()
        payload = app.feedback({"question": "Como melhorar a hidratação?", "answer": "Resposta testada", "correct": True})

        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["saved"])


if __name__ == "__main__":
    unittest.main()
