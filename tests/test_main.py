#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage --title="Code test coverage for trello-team-sync"

import unittest
import sys
import os
import logging
import json
from unittest.mock import patch
from unittest.mock import MagicMock
from unittest.mock import call

sys.path.append('.')
target = __import__("trello-team-sync")


class TestOutputSummary(unittest.TestCase):
    def test_output_summary_propagate(self):
        """
        Test the summary for --propagate
        """
        args = type("blabla", (object,), {
            "propagate": True,
            "cleanup": False,
            "dry_run": False})()
        summary = {"master_cards": 4,
            "active_master_cards": 2,
            "slave_card": 3,
            "new_slave_card": 1}
        with self.assertLogs(level='INFO') as cm:
            target.output_summary(args, summary)
        self.assertEqual(cm.output, [
            "INFO:root:================================================================",
            "INFO:root:Summary: processed 4 master cards (of which 2 active) that have 3 slave cards (of which 1 new)."])

    def test_output_summary_propagate_dry_run(self):
        """
        Test the summary for --propagate --dry-run
        """
        args = type("blabla", (object,), {
            "propagate": True,
            "cleanup": False,
            "dry_run": True})()
        summary = {"master_cards": 4,
            "active_master_cards": 2,
            "slave_card": 3,
            "new_slave_card": 1}
        with self.assertLogs(level='INFO') as cm:
            target.output_summary(args, summary)
        self.assertEqual(cm.output, [
            "INFO:root:================================================================",
            "INFO:root:Summary [DRY RUN]: processed 4 master cards (of which 2 active) that have 3 slave cards (of which 1 would have been new)."])

    def test_output_summary_cleanup(self):
        """
        Test the summary for --cleanup
        """
        args = type("blabla", (object,), {
            "propagate": False,
            "cleanup": True,
            "dry_run": False})()
        summary = {"cleaned_up_master_cards": 4,
            "deleted_slave_cards": 6,
            "erased_slave_boards": 2,
            "erased_slave_lists": 2}
        with self.assertLogs(level='INFO') as cm:
            target.output_summary(args, summary)
        self.assertEqual(cm.output, [
            "INFO:root:================================================================",
            "INFO:root:Summary: cleaned up 4 master cards and deleted 6 slave cards from 2 slave boards/2 slave lists."])

    def test_output_summary_cleanup_dry_run(self):
        """
        Test the summary for --cleanup --dry-run
        """
        args = type("blabla", (object,), {
            "propagate": False,
            "cleanup": True,
            "dry_run": True})()
        summary = {"cleaned_up_master_cards": 4,
            "deleted_slave_cards": 6,
            "erased_slave_boards": 2,
            "erased_slave_lists": 2}
        with self.assertLogs(level='INFO') as cm:
            target.output_summary(args, summary)
        self.assertEqual(cm.output, [
            "INFO:root:================================================================",
            "INFO:root:Summary [DRY RUN]: would have cleaned up 4 master cards and deleted 6 slave cards from 2 slave boards/2 slave lists."])


class TestGetCardAttachments(unittest.TestCase):
    def test_get_card_attachments_none(self):
        """
        Test retrieving attachments from a card without attachments
        """
        card = {"badges": {"attachments": 0}}
        card_attachments = target.get_card_attachments(None, card)
        self.assertEqual(card_attachments, [])

    @patch("trello-team-sync.perform_request")
    def test_get_card_attachments_non_trello(self, t_pr):
        """
        Test the logic retrieving attachments from a card without Trello attachments
        """
        t_pr.return_value = [{"url": "https://monip.org"}, {"url": "https://example.com"}]
        card = {"id": "1a2b3c", "badges": {"attachments": 2}}
        card_attachments = target.get_card_attachments(None, card)
        self.assertEqual(card_attachments, [])

    @patch("trello-team-sync.perform_request")
    def test_get_card_attachments_one_trello(self, t_pr):
        """
        Test retrieving attachments from a card with one Trello attachment
        """
        shortLink = "eoK0Rngb"
        t_pr.return_value = [{"url": "https://trello.com/c/%s/blablabla" % shortLink}]
        card = {"id": "1a2b3c", "badges": {"attachments": 1}}
        card_attachments = target.get_card_attachments(None, card)
        self.assertEqual(len(card_attachments), 1)
        expected_card_attachments = [{"card_shortUrl": shortLink,
            "url": "https://trello.com/c/%s/blablabla" % shortLink}]
        self.assertEqual(card_attachments, expected_card_attachments)

    @patch("trello-team-sync.perform_request")
    def test_get_card_attachments_various(self, t_pr):
        """
        Test retrieving attachments from a card with both Trello and non-Trello attachments
        """
        shortLink1 = "eoK0Rngb"
        shortLink2 = "abcd1234"
        t_pr.return_value = [{"url": "https://trello.com/c/%s/blablabla" % shortLink1},
            {"url": "https://monip.org"},
            {"url": "https://trello.com/c/%s/blablabla" % shortLink2}]
        card = {"id": "1a2b3c", "badges": {"attachments": 3}}
        card_attachments = target.get_card_attachments(None, card)
        self.assertEqual(len(card_attachments), 2)
        expected_card_attachments = [{"card_shortUrl": shortLink1,
            "url": "https://trello.com/c/%s/blablabla" % shortLink1},
            {"card_shortUrl": shortLink2,
            "url": "https://trello.com/c/%s/blablabla" % shortLink2}]
        self.assertEqual(card_attachments, expected_card_attachments)


class TestUpdateMasterCardMetadata(unittest.TestCase):
    @patch("trello-team-sync.perform_request")
    def test_update_master_card_metadata_both_none(self, t_pr):
        """
        Test updating a card that had no metadata with empty metadata
        """
        master_card = {"id": "1a2b3c", "desc": "abc"}
        target.update_master_card_metadata(None, master_card, "")
        # Confirm perform_request hasn't been called
        self.assertEqual(t_pr.mock_calls, [])

    @patch("trello-team-sync.perform_request")
    def test_update_master_card_metadata(self, t_pr):
        """
        Test updating a card that had no metadata with new metadata
        """
        master_card = {"id": "1a2b3c", "desc": "abc"}
        metadata = "jsdofhzpeh\nldjfozije"
        target.update_master_card_metadata(None, master_card, metadata)
        expected = [call(None, 'PUT', 'cards/1a2b3c',
            {'desc': 'abc\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\njsdofhzpeh\nldjfozije'})]
        self.assertEqual(t_pr.mock_calls, expected)

    @patch("trello-team-sync.perform_request")
    def test_update_master_card_metadata_empty(self, t_pr):
        """
        Test updating a card's that had metadata with empty metadata
        """
        main_desc = "abc"
        old_metadata = "old metadata"
        master_card = {"id": "1a2b3c", "desc": "%s%s%s" % (main_desc, target.METADATA_SEPARATOR, old_metadata) }
        target.update_master_card_metadata(None, master_card, "")
        expected = [call(None, 'PUT', 'cards/1a2b3c', {'desc': main_desc})]
        self.assertEqual(t_pr.mock_calls, expected)

    @patch("trello-team-sync.perform_request")
    def test_update_master_card_metadata_both(self, t_pr):
        """
        Test updating a card's that had metadata with new metadata
        """
        main_desc = "abc"
        old_metadata = "old metadata"
        master_card = {"id": "1a2b3c", "desc": "%s%s%s" % (main_desc, target.METADATA_SEPARATOR, old_metadata) }
        new_metadata = "new metadata"
        target.update_master_card_metadata(None, master_card, new_metadata)
        expected = [call(None, 'PUT', 'cards/1a2b3c',
            {'desc': "%s%s%s" % (main_desc, target.METADATA_SEPARATOR, new_metadata)})]
        self.assertEqual(t_pr.mock_calls, expected)

    @patch("trello-team-sync.perform_request")
    def test_update_master_card_metadata_same(self, t_pr):
        """
        Test updating a card's that had metadata with the same new metadata
        """
        main_desc = "abc"
        old_metadata = "old metadata"
        master_card = {"id": "1a2b3c", "desc": "%s%s%s" % (main_desc, target.METADATA_SEPARATOR, old_metadata) }
        target.update_master_card_metadata(None, master_card, old_metadata)
        # Confirm perform_request hasn't been called
        self.assertEqual(t_pr.mock_calls, [])


class TestSplitMasterCardMetadata(unittest.TestCase):
    def test_split_master_card_metadata_no_metadata(self):
        """
        Test splitting the master card description without metadata
        """
        full_desc = "ABC\nDEF"
        (main_desc, current_metadata) = target.split_master_card_metadata(full_desc)
        self.assertEqual(main_desc, full_desc)
        self.assertEqual(current_metadata, "")

    def test_split_master_card_metadata_partially_broken_metadata(self):
        """
        Test splitting the master card description with partially broken metadata
        """
        desc = "ABC\nDEFsldkjf"
        full_desc = "%s== DO NOT EDIT BELOW THIS LINEkhsfhizehf" % desc
        (main_desc, current_metadata) = target.split_master_card_metadata(full_desc)
        self.assertEqual(main_desc, desc + "== ")
        self.assertEqual(current_metadata, "")

    def test_split_master_card_metadata_fully_broken_metadata(self):
        """
        Test splitting the master card description with fully broken metadata
        """
        full_desc = "ABC\nDEFsldkjf\n== DO NOT EDIT BELOW THIS Lsfhizehf"
        (main_desc, current_metadata) = target.split_master_card_metadata(full_desc)
        self.assertEqual(main_desc, full_desc)
        self.assertEqual(current_metadata, "")

    def test_split_master_card_metadata_valid_metadata(self):
        """
        Test splitting the master card description with valid metadata
        """
        desc = "ABC\nDEFsldkjf"
        metadata = "jsdofhzpeh\nldjfozije"
        full_desc = "%s%s%s" % (desc, target.METADATA_SEPARATOR, metadata)
        (main_desc, current_metadata) = target.split_master_card_metadata(full_desc)
        self.assertEqual(main_desc, desc)
        self.assertEqual(current_metadata, metadata)


class TestGlobals(unittest.TestCase):
    def test_globals_metadata_phrase(self):
        """
        Test the METADATA_PHRASE global
        """
        self.assertEqual(target.METADATA_PHRASE, "DO NOT EDIT BELOW THIS LINE")

    def test_globals_metadata_separator(self):
        """
        Test the METADATA_SEPARATOR global
        """
        self.assertEqual(target.METADATA_SEPARATOR, "\n\n--------------------------------\n*== DO NOT EDIT BELOW THIS LINE ==*\n")


class TestLoadConfig(unittest.TestCase):
    def test_load_config(self):
        """
        Test loading a valid config file
        """
        config = target.load_config("data/sample_config.json")
        self.assertEqual(config["name"], "Sample configuration")
        self.assertEqual(config["key"], "abc")
        self.assertEqual(config["token"], "def")
        self.assertEqual(config["master_board"], "ghi")
        self.assertEqual(len(config["slave_boards"]), 2)
        self.assertEqual(len(config["slave_boards"]["Label One"]), 3)
        self.assertEqual(config["slave_boards"]["Label One"]["backlog"], "aaa")
        self.assertEqual(len(config["multiple_teams"]), 1)
        self.assertEqual(len(config["multiple_teams"]["All Teams"]), 2)
        self.assertEqual(config["multiple_teams"]["All Teams"][0], "Label One")
        self.assertEqual(config["multiple_teams_names"], ["All Teams"])

    def test_load_config_nonexisting(self):
        """
        Test loading a nonexisting config file
        """
        with self.assertRaises(FileNotFoundError) as cm:
            config = target.load_config("data/nonexisting_config.json")
        the_exception = cm.exception
        self.assertEqual(str(the_exception), "[Errno 2] No such file or directory: 'data/nonexisting_config.json'")

    def test_load_config_invalid(self):
        """
        Test loading an invalid config file (not json)
        """
        with self.assertRaises(json.decoder.JSONDecodeError) as cm:
            config = target.load_config("requirements.txt")
        the_exception = cm.exception
        self.assertEqual(str(the_exception), "Expecting value: line 1 column 1 (char 0)")


class TestParseArgs(unittest.TestCase):
    def test_parse_args_no_arguments(self):
        """
        Test running the script without one of the required arguments --propagate or --cleanup
        """
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args([])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 2)

    def test_parse_args_propagate_cleanup(self):
        """
        Test running the script with both mutually exclusive arguments --propagate and --cleanup
        """
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--cleanup'])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 2)

    def test_parse_args_debug(self):
        """
        Test the --debug argument
        """
        parser = target.parse_args(['--debug', '--propagate'])
        self.assertEqual(parser.loglevel, logging.DEBUG)
        self.assertEqual(parser.logging_level, "DEBUG")

    def test_parse_args_debug_shorthand(self):
        """
        Test the -d argument
        """
        parser = target.parse_args(['-d', '--propagate'])
        self.assertEqual(parser.loglevel, logging.DEBUG)
        self.assertEqual(parser.logging_level, "DEBUG")

    def test_parse_args_verbose(self):
        """
        Test the --verbose argument
        """
        parser = target.parse_args(['--verbose', '--propagate'])
        self.assertEqual(parser.loglevel, logging.INFO)
        self.assertEqual(parser.logging_level, "INFO")

    def test_parse_args_verbose_shorthand(self):
        """
        Test the -v argument
        """
        parser = target.parse_args(['-v', '--propagate'])
        self.assertEqual(parser.loglevel, logging.INFO)
        self.assertEqual(parser.logging_level, "INFO")

    def test_parse_args_propagate(self):
        """
        Test the --propagate argument
        """
        parser = target.parse_args(['--propagate'])
        self.assertTrue(parser.propagate)

    def test_parse_args_propagate_shorthand(self):
        """
        Test the -p argument
        """
        parser = target.parse_args(['-p'])
        self.assertTrue(parser.propagate)

    def test_parse_args_cleanup(self):
        """
        Test the --cleanup argument
        """
        parser = target.parse_args(['--cleanup', '--debug'])
        self.assertTrue(parser.cleanup)

    def test_parse_args_cleanup_shorthand(self):
        """
        Test the -cu argument
        """
        parser = target.parse_args(['-cu', '--debug'])
        self.assertTrue(parser.cleanup)

    def test_parse_args_valid_card8(self):
        """
        Test a valid 8-character --card parameter
        """
        shortLink = "eoK0Rngb"
        parser = target.parse_args(['--propagate', '--card', shortLink])
        self.assertEqual(parser.card, shortLink)

    def test_parse_args_valid_card24(self):
        """
        Test a valid 24-character --card parameter
        """
        card_id = "5ea946e30ea7437974b0ac9e"
        parser = target.parse_args(['--propagate', '--card', card_id])
        self.assertEqual(parser.card, card_id)

    def test_parse_args_valid_card_short_url(self):
        """
        Test a valid short card URL --card parameter
        """
        shortLink = "eoK0Rngb"
        url = "https://trello.com/c/%s" % shortLink
        parser = target.parse_args(['--propagate', '--card', url])
        self.assertEqual(parser.card, shortLink)

    def test_parse_args_valid_card_long_url(self):
        """
        Test a valid long card URL --card parameter
        """
        shortLink = "eoK0Rngb"
        url = "https://trello.com/c/%s/60-another-task-for-all-teams" % shortLink
        parser = target.parse_args(['--propagate', '--card', url])
        self.assertEqual(parser.card, shortLink)

    def test_parse_args_invalid_card8(self):
        """
        Test an invalid 8-character --card parameter
        """
        shortLink = "$oK0Rngb"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', shortLink])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 5)

    def test_parse_args_invalid_card24(self):
        """
        Test an invalid 24-character --card parameter
        """
        card_id = "5Ga946e30ea7437974b0ac9e"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', card_id])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 5)

    def test_parse_args_invalid_card_url(self):
        """
        Test an invalid card URL by passing a board URL as --card parameter
        """
        url = "https://trello.com/b/264nrPh8/test-scrum-of-scrums"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', url])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 5)

    def test_parse_args_card(self):
        """
        Test an invalid --card parameter
        """
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', 'abc'])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 5)

    def test_parse_args_valid_list24(self):
        """
        Test a valid 24-character --list parameter
        """
        list_id = "5ea6f86a46d1b9096faf6a72"
        parser = target.parse_args(['--propagate', '--list', list_id])
        self.assertEqual(parser.list, list_id)

    def test_parse_args_invalid_list24(self):
        """
        Test an invalid 24-character --list parameter
        """
        list_id = "5Ga6f86a46d1b9096faf6a72"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--list', list_id])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 7)

    def test_parse_args_list(self):
        """
        Test an invalid --list parameter
        """
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--list', 'abc'])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 7)

    def test_parse_args_cleanup_without_debug(self):
        """
        Test running the script with invalid arguments combination:
        --cleanup without --debug
        """
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--cleanup'])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 3)

    def test_parse_args_card_cleanup(self):
        """
        Test running the script with invalid arguments combination:
        --card with --cleanup
        """
        card_id = "5ea946e30ea7437974b0ac9e"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--cleanup', '--debug', '--card', card_id])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 4)

    def test_parse_args_list_cleanup(self):
        """
        Test running the script with invalid arguments combination:
        --list with --cleanup
        """
        list_id = "5ea6f86a46d1b9096faf6a72"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--cleanup', '--debug', '--list', list_id])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 6)

    def test_parse_args_dry_run(self):
        """
        Test the --dry-run argument
        """
        parser = target.parse_args(['--propagate', '--dry-run'])
        self.assertTrue(parser.dry_run)


#TODO
# class TestInitMain(unittest.TestCase):


class TestLicense(unittest.TestCase):
    def test_license_file(self):
        """Validate that the project has a LICENSE file, check part of its content"""
        self.assertTrue(os.path.isfile("LICENSE"))
        with open('LICENSE') as f:
            s = f.read()
            # Confirm it is the MIT License
            self.assertTrue("MIT License" in s)
            self.assertTrue("Copyright (c) 2020 Emilien Klein" in s)

    def test_license_mention(self):
        """Validate that the script file contain a mention of the license"""
        with open('trello-team-sync.py') as f:
            s = f.read()
            # Confirm it is the MIT License
            self.assertTrue("#    This file is part of trello-team-sync and is MIT-licensed." in s)


if __name__ == '__main__':
    unittest.main()
