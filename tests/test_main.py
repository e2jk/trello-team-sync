#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage --title="Code test coverage for trello-team-sync"

import unittest
import sys
import os
import shutil
import logging
import socket
import json
import tempfile
from urllib.error import URLError
from unittest.mock import patch
from unittest.mock import MagicMock

sys.path.append('.')
target = __import__("trello-team-sync")


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

    def test_parse_args_valid_card32(self):
        """
        Test a valid 32-character --card parameter
        """
        card_id = "5ea946e30ea7437974b0ac9e"
        parser = target.parse_args(['--propagate', '--card', card_id])
        self.assertEqual(parser.card, card_id)

    def test_parse_args_invalid_card8(self):
        """
        Test an invalid 8-character --card parameter
        """
        shortLink = "$oK0Rngb"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', shortLink])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 5)

    def test_parse_args_invalid_card32(self):
        """
        Test an invalid 32-character --card parameter
        """
        card_id = "5Ga946e30ea7437974b0ac9e"
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--propagate', '--card', card_id])
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
        with self.assertRaises(SystemExit) as cm:
            parser = target.parse_args(['--cleanup', '--debug', '--card', 'abc'])
        the_exception = cm.exception
        self.assertEqual(the_exception.code, 4)

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
