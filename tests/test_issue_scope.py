import unittest
from task_tower.issue_intake import validate_issue_diff,INITIAL_POLICY
DIFF="diff --git a/docs/example.md b/docs/example.md\nindex 1234567..7654321 100644\n--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n"
class ScopeTests(unittest.TestCase):
    def test_only_declared_regular_text_change_can_reach_review(self):
        validate_issue_diff(DIFF,["docs/example.md"],INITIAL_POLICY)
        for text in [DIFF.replace("100644","120000"),DIFF.replace("docs/example.md","README.md"),DIFF+"GIT binary patch\n",DIFF.replace("index 1234567..7654321 100644","deleted file mode 100644")]:
            with self.subTest(text=text),self.assertRaises(ValueError):validate_issue_diff(text,["docs/example.md"],INITIAL_POLICY)
