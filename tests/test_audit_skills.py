"""Regression tests for audit_skills.py. Standard library only.

Run from the repository root:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills" / "skill-audit" / "scripts" / "audit_skills.py"
)
_spec = importlib.util.spec_from_file_location("audit_skills", SCRIPT)
assert _spec is not None and _spec.loader is not None
audit = importlib.util.module_from_spec(_spec)
# dataclasses resolves annotations through sys.modules, so register first.
sys.modules["audit_skills"] = audit
_spec.loader.exec_module(audit)


def write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


class TriggerLanguage(unittest.TestCase):
    def test_recognised_phrasings(self) -> None:
        for text in [
            "Use when the user asks for X.",
            "Use this when drafting.",
            "Use it when drafting.",
            "Use this skill when a user asks to analyze an RFP.",
            "Use this agent when the user wants a review.",
            "Use PROACTIVELY after drafts are completed.",
            "Triggered when someone says audit.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(audit.has_trigger_language(text))

    def test_what_without_when_still_flags(self) -> None:
        self.assertFalse(audit.has_trigger_language(
            "Analyzes RFPs and produces a compliance checklist."
        ))


class SkillGrading(unittest.TestCase):
    def test_use_this_skill_when_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "skills/rfp-analysis/SKILL.md", """
                ---
                name: rfp-analysis
                description: Analyzes RFPs for the firm. Use this skill when a user asks to analyze an RFP.
                ---
                body
            """)
            [skill] = audit.find_skills([root])
            audit.grade(skill)
            self.assertEqual(skill.defects, [])

    def test_unread_triggers_key_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "skills/proposal-development/SKILL.md", """
                ---
                name: proposal-development
                description: >
                  Use when writing a proposal for the firm, a section, or an outline.
                triggers:
                  - write a proposal
                ---
                body
            """)
            [skill] = audit.find_skills([root])
            audit.grade(skill)
            self.assertEqual(len(skill.defects), 1)
            self.assertIn("'triggers' is not read", skill.defects[0])


class AgentGrading(unittest.TestCase):
    LEGACY = """
        ---
        identifier: proposal-writer
        description: >
          Proposal drafting specialist for the firm. Writes proposal sections.
        whenToUse: >
          Use this agent when the user wants to write proposal content.
        model: claude-sonnet-4-20250514
        ---
        You write proposals.
    """

    def test_legacy_agent_header_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "my-plugin/agents/proposal-writer.md", self.LEGACY)
            [agent] = audit.find_agents([root])
            audit.grade_agent(agent)
            joined = "\n".join(agent.defects)
            self.assertIn("no name in frontmatter", joined)
            self.assertIn("'identifier' is not read", joined)
            self.assertIn("'whenToUse' is not read", joined)
            # The when-text is stranded in whenToUse, so description lacks it.
            self.assertIn("never when to delegate", joined)

    def test_fixed_agent_header_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "my-plugin/agents/proposal-writer.md", """
                ---
                name: proposal-writer
                description: >
                  Drafts proposal content for the firm. Use when the user asks to
                  write, draft, or outline a proposal.
                model: sonnet
                ---
                You write proposals.
            """)
            [agent] = audit.find_agents([root])
            audit.grade_agent(agent)
            self.assertEqual(agent.defects, [])

    def test_agent_without_frontmatter_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "my-plugin/agents/README.md", "# Notes about our agents\n")
            [agent] = audit.find_agents([root])
            audit.grade_agent(agent)
            self.assertEqual(agent.defects, [])

    def test_agents_affect_exit_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "my-plugin/agents/proposal-writer.md", self.LEGACY)
            with redirect_stdout(io.StringIO()) as out:
                status = audit.main([str(root), "--quiet"])
            self.assertEqual(status, 1)
            self.assertIn("1 agents flagged", out.getvalue())


if __name__ == "__main__":
    unittest.main()
