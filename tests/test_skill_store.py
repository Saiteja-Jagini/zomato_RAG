import pathlib
import sqlite3
import tempfile
import unittest
from contextlib import closing

from skill_store import (
    PLOTTING_SKILL_ID,
    PLOTTING_SKILL_PATH,
    initialize_skill_store,
    load_skill,
    record_skill_execution,
    validate_payload,
)


class SkillStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temporary_directory.name) / "skills.db"
        initialize_skill_store(
            db_path=self.db_path,
            skill_path=PLOTTING_SKILL_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_database_record_is_runtime_source_of_truth(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "UPDATE skills SET prompt_template = ? WHERE skill_id = ?",
                ("Database-owned prompt", PLOTTING_SKILL_ID),
            )
            connection.commit()

        initialize_skill_store(
            db_path=self.db_path,
            skill_path=pathlib.Path(self.temporary_directory.name) / "missing.md",
        )
        skill = load_skill(PLOTTING_SKILL_ID, db_path=self.db_path)

        self.assertEqual(skill.prompt_template, "Database-owned prompt")
        self.assertEqual(skill.scope, "analytics.visualization")
        self.assertEqual(skill.status, "active")
        self.assertIn("model", skill.configuration)

    def test_input_contract_rejects_missing_rows(self):
        skill = load_skill(PLOTTING_SKILL_ID, db_path=self.db_path)

        with self.assertRaisesRegex(ValueError, "rows is required"):
            validate_payload(
                {
                    "python_script": "fig, ax = plt.subplots()",
                    "data": {"columns": ["name"]},
                    "chart_name": "sample",
                },
                skill.input_schema,
                "skill_input",
            )

    def test_execution_history_updates_autonomy(self):
        skill = load_skill(PLOTTING_SKILL_ID, db_path=self.db_path)
        input_payload = {
            "python_script": "fig, ax = plt.subplots()",
            "data": {"columns": ["name"], "rows": [["example"]]},
            "chart_name": "sample",
        }

        for _ in range(4):
            summary = record_skill_execution(
                skill,
                input_payload=input_payload,
                output_payload={"success": True, "image_path": "outputs/test.png"},
                duration_ms=10,
                db_path=self.db_path,
            )
            self.assertEqual(summary.autonomy_level, "supervised")

        summary = record_skill_execution(
            skill,
            input_payload=input_payload,
            output_payload={"success": False, "error": "test failure"},
            duration_ms=5,
            db_path=self.db_path,
        )
        self.assertEqual(summary.total_executions, 5)
        self.assertEqual(summary.successful_executions, 4)
        self.assertEqual(summary.success_rate, 0.8)
        self.assertEqual(summary.autonomy_level, "autonomous")

        summary = record_skill_execution(
            skill,
            input_payload=input_payload,
            output_payload={"success": False, "error": "another failure"},
            duration_ms=5,
            db_path=self.db_path,
        )
        self.assertEqual(summary.autonomy_level, "supervised")


if __name__ == "__main__":
    unittest.main()
