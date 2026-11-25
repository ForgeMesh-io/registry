import unittest

from build_site import leaderboard, summarise


class PortalTests(unittest.TestCase):
    def test_counts_and_credit_use_published_state_not_claim_volume(self):
        state = {"clock": "2026-01-01T00:00:00Z", "tasks": {
            "NX-0001": {"status": "MERGED", "display_status": "MERGED", "claimant": "AlIce",
                "submission": {"pr": 8, "author": "AlIce", "head_sha": "a", "audit": []},
                "votes": {"Bob": {"sha": "a", "verdict": "pass"}, "Eve": {"sha": "b", "verdict": "pass"}}},
            "NX-0002": {"status": "CLAIMED", "display_status": "CLAIMED", "claimant": "Bob"},
            "NX-0003": {"status": "MERGED", "display_status": "MERGED", "claimant": "Eve",
                "submission": {"pr": 9, "author": "Eve", "head_sha": "z", "audit": ["merged while SUBMITTED"]}},
            "NX-0004": {"status": "MERGED", "display_status": "MERGED",
                "submission": {"pr": 8, "author": "alice", "head_sha": "a", "audit": []}},
        }}
        stats = summarise(state)
        self.assertEqual(stats["active_participants"], 1)
        self.assertEqual(stats["counts"], {"MERGED": 3, "CLAIMED": 1})
        rows = leaderboard([("nexus", state), ("vie", None)])
        by_login = {r["login"].lower(): r for r in rows}
        self.assertEqual([(r["login"], r["merged"], r["validations"]) for r in rows], [("AlIce", 1, 0), ("Bob", 0, 1)])
        self.assertEqual(by_login["alice"]["projects"]["nexus"]["merged"], 1)
        self.assertEqual(by_login["bob"]["projects"]["nexus"]["validations"], 1)

    def test_unavailable_data_is_distinct_from_an_empty_swarm(self):
        self.assertIsNone(summarise(None))
        self.assertEqual(summarise({"tasks": {}})["tasks"], [])
        self.assertEqual(leaderboard([("nexus", None)]), [])


if __name__ == "__main__":
    unittest.main()
