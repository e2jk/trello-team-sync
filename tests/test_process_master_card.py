#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && \
#   rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage \
#   --title="Code test coverage for trello-team-sync"

import unittest
import sys
from unittest.mock import patch
import inspect

sys.path.append('.')
target = __import__("trello_team_sync")


class TestProcessMasterCard(unittest.TestCase):
    def test_process_master_card_0(self):
        """
        Test processing a new master card without labels or attachments
        """
        target.config = {"key": "ghi", "token": "jkl", "destination_lists": []}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [], "badges": {"attachments": 0}}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (0, 0, 0))
        self.assertEqual(cm.output, ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 0 destination lists',
            'INFO:root:This master card has no slave cards'])

    def test_process_master_card_unknown_label(self):
        """
        Test processing a new master card with one label that is not in the config
        """
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "Unknown label"}], "badges": {"attachments": 0}}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (0, 0, 0))
        self.assertEqual(cm.output, ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 0 destination lists',
            'INFO:root:This master card has no slave cards'])

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_one_label(self, t_pr):
        """
        Test processing a new master card with one recognized label
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 destination lists',
            'DEBUG:root:Creating new slave card',
            'DEBUG:root:New slave card ID: bbbbbbbbbbbbbbbbbbbbbbbb',
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (1 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'",
            'DEBUG:root:Attaching master card tttttttttttttttttttttttt to slave card bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching slave card bbbbbbbbbbbbbbbbbbbbbbbb to master card tttttttttttttttttttttttt']
        self.assertEqual(cm.output, expected)
        target.args = None

    def test_process_master_card_label_multiple(self):
        """
        Test processing a new master card with one label that maps to multiple lists
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "All Teams"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb"}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 2, 2))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 2 destination lists',
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'INFO:root:This master card has 2 slave cards (2 newly created)']
        self.assertEqual(cm.output, expected)
        target.args = None

    def test_process_master_card_label_multiple_and_duplicate_single(self):
        """
        Test processing a new master card with one label that maps to multiple lists and another single label that was already in the multiple list
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "1a2b3c", "desc": "abc", "name": "Card name",
            "labels": [{"name": "All Teams"}, {"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb"}
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 2, 2))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 2 destination lists',
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'DEBUG:root:Creating new slave card',
            "DEBUG:root:Skipping POST call to 'https://api.trello.com/1/cards' due to --dry-run parameter",
            'INFO:root:This master card has 2 slave cards (2 newly created)']
        self.assertEqual(cm.output, expected)
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_dummy_attachment(self, t_pr):
        """
        Test processing a new master card with one non-Trello attachment
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 1},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [[{"id": "rrr", "url": "https://monip.org"}],
            {"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 destination lists',
            'DEBUG:root:Getting 1 attachments on master card tttttttttttttttttttttttt',
            'DEBUG:root:Creating new slave card',
            'DEBUG:root:New slave card ID: bbbbbbbbbbbbbbbbbbbbbbbb',
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (1 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'",
            'DEBUG:root:Attaching master card tttttttttttttttttttttttt to slave card bbbbbbbbbbbbbbbbbbbbbbbb',
            'DEBUG:root:Attaching slave card bbbbbbbbbbbbbbbbbbbbbbbb to master card tttttttttttttttttttttttt']
        self.assertEqual(cm.output, expected)
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_attachment(self, t_pr):
        """
        Test processing a new master card with one Trello attachment
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["aaa"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "aaa",
                  "ddd"
                ]
            }}
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
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 0))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 1 destination lists',
            'DEBUG:root:Getting 1 attachments on master card tttttttttttttttttttttttt',
            "DEBUG:root:Slave card qqqqqqqqqqqqqqqqqqqqqqqq already exists on list aaa",
            "DEBUG:root:{'id': 'qqqqqqqqqqqqqqqqqqqqqqqq', 'name': 'Slave card One', 'idBoard': 'kkkkkkkkkkkkkkkkkkkkkkkk', 'idList': 'aaa'}",
            "DEBUG:root:New master card metadata: \n- 'Slave card One' on list '**Board name|List name**'",
            'INFO:root:This master card has 1 slave cards (0 newly created)',
            'DEBUG:root:Updating master card metadata',
            "DEBUG:root:abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n\n- 'Slave card One' on list '**Board name|List name**'"]
        self.assertEqual(cm.output, expected)
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_attachment_no_label(self, t_pr):
        """
        Test processing a new master card with one Trello attachment but no label
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": True})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [], "badges": {"attachments": 1},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [[{"id": "rrr", "url": "https://trello.com/c/abcd1234/blablabla4"}],
            {"id": "q"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "aaa"},
            {"name": "Board name"},
            {"name": "List name"},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (0, 0, 0))
        expected = ['DEBUG:root:================================================================',
            "DEBUG:root:Process master card 'Card name'",
            'DEBUG:root:Master card is to be synced on 0 destination lists',
            'DEBUG:root:Getting 1 attachments on master card tttttttttttttttttttttttt',
            "DEBUG:root:Master card has been unlinked from slave cards",
            "INFO:root:This master card has no slave cards"]
        self.assertEqual(cm.output, expected)
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_one_label_wet_run_no_checklist(self, t_pr):
        """
        Test processing a new master card with one recognized label, no dry_run, without a checklist
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": False})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            },
            "friendly_names": {
                "Label Two": "Nicer Label"
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            [],
            {"id": "w"*24, "name": "New checklist"},
            {"idBoard": "hhh"},
            {"name": "Destination board name"},
            {"name": "New checklist item"},
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = "\n".join(["DEBUG:root:Retrieving checklists from card tttttttttttttttttttttttt",
            "DEBUG:root:Creating new checklist",
            "DEBUG:root:{'id': 'wwwwwwwwwwwwwwwwwwwwwwww', 'name': 'New checklist'}",
            "DEBUG:root:Adding new checklistitem 'Destination board name' to checklist wwwwwwwwwwwwwwwwwwwwwwww",
            "DEBUG:root:{'name': 'New checklist item'}"])
        self.assertTrue(expected in "\n".join(cm.output))
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_one_label_wet_run_unrelated_checklist(self, t_pr):
        """
        Test processing a new master card with one recognized label, no dry_run, with one unrelated checklist
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": False})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["aaa"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "aaa",
                  "ddd"
                ]
            },
            "friendly_names": {
                "Label Two": "Nicer Label"
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            [{"name": "Unrelated checklist"}],
            {"id": "w"*24, "name": "New checklist"},
            {"idBoard": "hhh"},
            {"name": "Destination board name"},
            {"name": "New checklist item"},
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = "\n".join(["DEBUG:root:Retrieving checklists from card tttttttttttttttttttttttt",
            "DEBUG:root:Already 1 checklists on this master card: Unrelated checklist",
            "DEBUG:root:Creating new checklist",
            "DEBUG:root:{'id': 'wwwwwwwwwwwwwwwwwwwwwwww', 'name': 'New checklist'}",
            "DEBUG:root:Adding new checklistitem 'Destination board name' to checklist wwwwwwwwwwwwwwwwwwwwwwww",
            "DEBUG:root:{'name': 'New checklist item'}"])
        self.assertTrue(expected in "\n".join(cm.output))
        target.args = None


    @patch("trello_team_sync.perform_request")
    def test_process_master_card_one_label_wet_run_friendly_name_checklist(self, t_pr):
        """
        Test processing a new master card with one recognized label, no dry_run,
        without a checklist and using a friendly name as checklist item instead of the board's name
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": False})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            },
            "friendly_names": {
                "Destination board name": "Nicer Label"
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            [],
            {"id": "w"*24, "name": "New checklist"},
            {"idBoard": "hhh"},
            {"name": "Destination board name"},
            {"name": "New checklist item"},
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = "\n".join(["DEBUG:root:Retrieving checklists from card tttttttttttttttttttttttt",
            "DEBUG:root:Creating new checklist",
            "DEBUG:root:{'id': 'wwwwwwwwwwwwwwwwwwwwwwww', 'name': 'New checklist'}",
            "DEBUG:root:Adding new checklistitem 'Nicer Label' to checklist wwwwwwwwwwwwwwwwwwwwwwww",
            "DEBUG:root:{'name': 'New checklist item'}"])
        self.assertTrue(expected in "\n".join(cm.output))
        target.args = None

    @patch("trello_team_sync.perform_request")
    def test_process_master_card_one_label_wet_run_related_checklist(self, t_pr):
        """
        Test processing a new master card with one recognized label, no dry_run, with already the related checklist
        """
        target.args = type(inspect.stack()[0][3], (object,), {"dry_run": False})()
        target.config = {"key": "ghi", "token": "jkl",
            "destination_lists": {
                "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
                "Label Two": ["ddd"],
                "All Teams": [
                  "a1a1a1a1a1a1a1a1a1a1a1a1",
                  "ddd"
                ]
            }}
        master_card = {"id": "t"*24, "desc": "abc", "name": "Card name",
            "labels": [{"name": "Label One"}], "badges": {"attachments": 0},
            "shortUrl": "https://trello.com/c/eoK0Rngb",
            "url": "https://trello.com/c/eoK0Rngb/blablabla"}
        t_pr.side_effect = [{"id": "b"*24, "name": "Slave card One",
                "idBoard": "k"*24, "idList": "l"*24,
                "url": "https://trello.com/c/abcd1234/blablabla2"},
            {"name": "Board name"},
            {"name": "List name"},
            {},
            [{"name": "Involved Teams"}],
            {},
            {}]
        with self.assertLogs(level='DEBUG') as cm:
            output = target.process_master_card(master_card)
        self.assertEqual(output, (1, 1, 1))
        expected = "\n".join(["DEBUG:root:Retrieving checklists from card tttttttttttttttttttttttt",
            "DEBUG:root:Already 1 checklists on this master card: Involved Teams"])
        self.assertTrue(expected in "\n".join(cm.output))
        target.args = None
        target.config


if __name__ == '__main__':
    unittest.main()
