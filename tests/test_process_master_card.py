#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage --title="Code test coverage for trello-team-sync"

import unittest
import sys
from unittest.mock import patch
from unittest.mock import call

sys.path.append('.')
target = __import__("trello-team-sync")


class TestProcessMasterCard(unittest.TestCase):
    def test_process_master_card_0(self):
        """
        Test processing a new master card without labels or attachments
        """
        config = {"key": "ghi", "token": "jkl"}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [], "badges": {"attachments": 0}}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (0, 0, 0))
        self.assertEqual(cm.output, ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 0 slave boards ()',
            'INFO:root:This master card has no slave cards'])

    def test_process_master_card_unknown_label(self):
        """
        Test processing a new master card with one label that is not in the config
        """
        config = {"key": "ghi", "token": "jkl", "multiple_teams": {}, "multiple_teams_names": [],
            "slave_boards": {"Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"}}}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "Unknown label"}], "badges": {"attachments": 0}}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (0, 0, 0))
        self.assertEqual(cm.output, ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 0 slave boards ()',
            'INFO:root:This master card has no slave cards'])

    @patch("trello-team-sync.perform_request")
    def test_process_master_card_one_label(self, t_pr):
        """
        Test processing a new master card with one recognized label
        """
        config = {"key": "ghi", "token": "jkl", "multiple_teams": {}, "multiple_teams_names": [],
            "slave_boards": {"Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"}}}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {},
            {},
            {"name": "Board name"},
            {"name": "List name"},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 slave boards (Label One)',
            'DEBUG:root:Creating new slave card',
            'DEBUG:root:New slave card ID: bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching master card tttttttttttttttttttttttt to slave card bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching slave card bbbbbbbbbbbbbbbbbbbbbbbb to master card tttttttttttttttttttttttt',
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (1 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'"]
        self.assertEqual(cm.output, expected)

    def test_process_master_card_label_multiple(self):
        """
        Test processing a new master card with one label that maps to multiple lists
        """
        config = {"key": "ghi", "token": "jkl",
            "slave_boards": {
                "Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"},
                "Label Two": {"backlog": "ddd", "in_progress": "eee", "complete": "fff"}},
            "multiple_teams": {"All Teams": ["Label One", "Label Two"]},
            "multiple_teams_names": ["All Teams"]}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "All Teams"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb"}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (1, 2, 2))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Syncing this master card to multiple boards at once',
            'DEBUG:root:Master card is to be synced on 2 slave boards (Label One, Label Two)',
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'INFO:root:This master card has 2 slave cards (2 newly created)']
        self.assertEqual(cm.output, expected)

    def test_process_master_card_label_multiple_and_duplicate_single(self):
        """
        Test processing a new master card with one label that maps to multiple lists and another single label that was already in the multiple list
        """
        config = {"key": "ghi", "token": "jkl",
            "slave_boards": {
                "Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"},
                "Label Two": {"backlog": "ddd", "in_progress": "eee", "complete": "fff"}},
            "multiple_teams": {"All Teams": ["Label One", "Label Two"]},
            "multiple_teams_names": ["All Teams"]}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "All Teams"}, {"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb"}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (1, 2, 2))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Syncing this master card to multiple boards at once',
            'DEBUG:root:Master card is to be synced on 2 slave boards (Label One, Label Two)',
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'INFO:root:This master card has 2 slave cards (2 newly created)']
        self.assertEqual(cm.output, expected)

    @patch("trello-team-sync.perform_request")
    def test_process_master_card_dummy_attachment(self, t_pr):
        """
        Test processing a new master card with one non-Trello attachment
        """
        config = {"key": "ghi", "token": "jkl", "multiple_teams": {}, "multiple_teams_names": [],
            "slave_boards": {"Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"}}}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 1},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [[{"id": "rrr", "url": "https://monip.org"}],
            {"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {},
            {},
            {"name": "Board name"},
            {"name": "List name"},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 slave boards (Label One)',
            'DEBUG:root:Getting 1 attachments on master card tttttttttttttttttttttttt',
            'DEBUG:root:Creating new slave card',
            'DEBUG:root:New slave card ID: bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching master card tttttttttttttttttttttttt to slave card bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching slave card bbbbbbbbbbbbbbbbbbbbbbbb to master card tttttttttttttttttttttttt',
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (1 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'"]
        self.assertEqual(cm.output, expected)

    @patch("trello-team-sync.perform_request")
    def test_process_master_card_attachment(self, t_pr):
        """
        Test processing a new master card with one Trello attachment
        """
        config = {"key": "ghi", "token": "jkl", "multiple_teams": {}, "multiple_teams_names": [],
            "slave_boards": {"Label One": {"backlog": "aaa", "in_progress": "bbb", "complete": "ccc"}}}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 1},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [[{"id": "rrr", "url": "https://trello.com/c/abcd1234/blablabla4"}],
            {"id": "q"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "aaa"},
            {"name": "Board name"},
            {"name": "List name"},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(config, master_card)
        self.assertEqual(output, (1, 1, 0))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 slave boards (Label One)',
            'DEBUG:root:Getting 1 attachments on master card tttttttttttttttttttttttt',
            "DEBUG:root:Slave card qqqqqqqqqqqqqqqqqqqqqqqq already exists on board Label One",
            "DEBUG:root:{'id': 'qqqqqqqqqqqqqqqqqqqqqqqq', 'name': 'Slave card One', 'idBoard': 'kkkkkkkkkkkkkkkkkkkkkkkk', 'idList': 'aaa'}",
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (0 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'"]
        self.assertEqual(cm.output, expected)


if __name__ == '__main__':
    unittest.main()
