#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.

import argparse
import logging
import json
import requests
import os
import sys
import re

METADATA_PHRASE = "DO NOT EDIT BELOW THIS LINE"
METADATA_SEPARATOR = "\n\n%s\n*== %s ==*\n" % ("-" * 32, METADATA_PHRASE)

def output_summary(args, summary):
    logging.info("="*64)
    if args.cleanup:
        logging.info("Summary: cleaned up %d master cards and deleted %d slave cards from %d slave boards/%d slave lists." % (
            summary["master_cards"],
            summary["deleted_slave_cards"],
            summary["erased_slave_boards"],
            summary["erased_slave_lists"]))
    elif args.propagate:
        logging.info("Summary: processed %d master cards that have %d slave cards (of which %d new)." % (
            summary["master_cards"],
            summary["slave_card"],
            summary["new_slave_card"]))

def remove_teams_checklist(config, master_card):
    master_card_checklists = get_card_checklists(config, master_card)
    for c in master_card_checklists:
        if "Involved Teams" == c["name"]:
            logging.debug("Deleting checklist %s (%s) from master card %s" %(c["name"], c["id"], master_card["id"]))
            url = "https://api.trello.com/1/checklists/%s" % (c["id"])
            url += "?key=%s&token=%s" % (config["key"], config["token"])
            response = requests.request(
               "DELETE",
               url
            )

def add_checklistitem_to_checklist(config, checklist_id, item_name):
    logging.debug("Adding new checklistitem %s to checklist %s" % (item_name, checklist_id))
    url = "https://api.trello.com/1/checklists/%s/checkItems" % checklist_id
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    query = {
       "name": item_name
    }
    response = requests.request(
        "POST",
        url,
        params=query
    )
    new_checklistitem = response.json()
    logging.debug(new_checklistitem)
    return new_checklistitem

def add_checklist_to_master_card(config, master_card):
    logging.debug("Creating new checklist")
    url = "https://api.trello.com/1/cards/%s/checklists" % master_card["id"]
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    query = {
       "name": "Involved Teams"
    }
    response = requests.request(
        "POST",
        url,
        params=query
    )
    new_checklist = response.json()
    logging.debug(new_checklist)
    return new_checklist

def get_card_checklists(config, master_card):
    logging.debug("Retrieving checklists from card %s" % master_card["id"])
    url = "https://api.trello.com/1/cards/%s/checklists" % master_card["id"]
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    response = requests.request(
       "GET",
       url
    )
    return response.json()

def attach_slave_card_to_master_card(config, master_card, slave_card):
    logging.debug("Attaching slave card %s to master card %s" % (slave_card["id"], master_card["id"]))
    url = "https://api.trello.com/1/cards/%s/attachments" % master_card["id"]
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    query = {
       "url": slave_card["url"]
    }
    response = requests.request(
        "POST",
        url,
        params=query
    )

def get_card_attachments(config, card):
    card_attachments = []
    if card["badges"]["attachments"] > 0:
        logging.debug("Getting %d attachments on master card %s" % (card["badges"]["attachments"], card["id"]))
        url = "https://api.trello.com/1/cards/%s/attachments" % card["id"]
        url += "?key=%s&token=%s" % (config["key"], config["token"])
        response = requests.request(
           "GET",
           url
        )
        for a in response.json():
            # Only keep attachments that are links to other Trello cards
            card_shorturl_regex = "https://trello.com/c/([a-zA-Z0-9_-]{8})/.*"
            card_shorturl_regex_match = re.match(card_shorturl_regex, a["url"])
            if card_shorturl_regex_match:
                a["card_shortUrl"] = card_shorturl_regex_match.group(1)
                card_attachments.append(a)
    return card_attachments

def cleanup_test_boards(config, master_cards):
    logging.debug("Removing slave cards attachments on the master cards")
    for idx, master_card in enumerate(master_cards):
        logging.debug("="*64)
        logging.info("Cleaning up master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
        master_card_attachments = get_card_attachments(config, master_card)
        if len(master_card_attachments) > 0:
            for a in master_card_attachments:
                logging.debug("Deleting attachment %s from master card %s" %(a["id"], master_card["id"]))
                url = "https://api.trello.com/1/cards/%s/attachments/%s" % (master_card["id"], a["id"])
                url += "?key=%s&token=%s" % (config["key"], config["token"])
                response = requests.request(
                   "DELETE",
                   url
                )

        # Removing teams checklist from the master card
        remove_teams_checklist(config, master_card)

        # Removing metadata from the master cards
        update_master_card_metadata(config, master_card, "")

    logging.debug("Deleting slave cards")
    num_lists_to_cleanup = 0
    num_lists_cleanedup = 0
    deleted_slave_cards = 0
    for sb in config["slave_boards"]:
        for l in config["slave_boards"][sb]:
            num_lists_to_cleanup += 1
    for sb in config["slave_boards"]:
        for l in config["slave_boards"][sb]:
            logging.debug("="*64)
            num_lists_cleanedup += 1
            logging.debug("Retrieve cards from list %s|%s (list %d/%d)" % (sb, l, num_lists_cleanedup, num_lists_to_cleanup))
            url = "https://api.trello.com/1/lists/%s/cards" % config["slave_boards"][sb][l]
            url += "?key=%s&token=%s" % (config["key"], config["token"])
            response = requests.request(
               "GET",
               url
            )
            slave_cards = response.json()
            logging.debug(slave_cards)
            logging.debug("List %s/%s has %d cards to delete" % (sb, l, len(slave_cards)))
            for sc in slave_cards:
                logging.debug("Deleting slave card %s" % sc["id"])
                deleted_slave_cards += 1
                url = "https://api.trello.com/1/cards/%s" % sc["id"]
                url += "?key=%s&token=%s" % (config["key"], config["token"])
                response = requests.request(
                   "DELETE",
                   url
                )
    return {"master_cards": len(master_cards),
            "deleted_slave_cards": deleted_slave_cards,
            "erased_slave_boards": len(config["slave_boards"]),
            "erased_slave_lists": num_lists_cleanedup}

def split_master_card_metadata(master_card_desc):
    if METADATA_SEPARATOR not in master_card_desc:
        if METADATA_PHRASE not in master_card_desc:
            return [master_card_desc, ""]
        else:
            # Somebody has messed with the line, but the main text is still visible
            # Cut off at that text
            return [master_card_desc[:master_card_desc.find(METADATA_PHRASE)], ""]

    else:
        # Split the main description from the metadata added after the separator
        regex_pattern = "^(.*)(%s)(.*)" % re.escape(METADATA_SEPARATOR)
        match = re.search(regex_pattern, master_card_desc, re.DOTALL)
        return [match.group(1), match.group(3)]

def update_master_card_metadata(config, master_card, new_master_card_metadata):
    (main_desc, current_master_card_metadata) = split_master_card_metadata(master_card["desc"])
    if new_master_card_metadata != current_master_card_metadata:
        logging.debug("Updating master card metadata")
        if new_master_card_metadata:
            new_full_desc = "%s%s%s" % (main_desc, METADATA_SEPARATOR, new_master_card_metadata)
        else:
            # Also remove the metadata separator when removing the metadata
            new_full_desc = main_desc
        logging.debug(new_full_desc)
        url = "https://api.trello.com/1/cards/%s" % master_card["id"]
        url += "?key=%s&token=%s" % (config["key"], config["token"])
        query = {
           "desc": new_full_desc
        }
        response = requests.request(
            "PUT",
            url,
            params=query
        )

def get_name(config, record_type, record_id):
    #TODO: Cache board/list names
    url = "https://api.trello.com/1/%s/%s" % (record_type, record_id)
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    response = requests.request(
       "GET",
       url
    )
    return response.json()["name"]

def generate_master_card_metadata(config, slave_cards):
    mcm = ""
    for sc in slave_cards:
        mcm += "\n- '%s' on list '**%s|%s**'" % (sc["name"],
            get_name(config, "board", sc["idBoard"]),
            get_name(config, "list", sc["idList"]))
    logging.debug("New master card metadata: %s" % mcm)
    return mcm

def create_new_slave_card(config, master_card, slave_board):
    logging.debug("Creating new slave card")
    url = "https://api.trello.com/1/cards"
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    query = {
       "idList": slave_board["lists"]["backlog"],
       "name": master_card["name"],
       "desc": "%s\n\nCreated from master card %s" % (master_card["desc"], master_card["shortUrl"]),
       "pos": "bottom",
       "urlSource": master_card["shortUrl"]
    }
    response = requests.request(
        "POST",
        url,
        params=query
    )
    new_slave_card = response.json()
    logging.debug(new_slave_card)
    return new_slave_card

def process_master_card(config, master_card):
    logging.debug("="*64)
    logging.debug("Process master card '%s'" % master_card["name"])
    # Check if this card is to be synced on a slave board
    full_slave_boards = []
    for l in master_card["labels"]:
        # Handle labels that add to multiple lists at once
        if l["name"] in config["multiple_teams_names"]:
            logging.debug("Syncing this master card to multiple boards at once")
            for sb in config["multiple_teams"][l["name"]]:
                full_slave_boards.append({"name": sb, "lists": config["slave_boards"][sb]})
        else:
            if l["name"] in config["slave_boards"]:
                full_slave_boards.append({"name": l["name"], "lists": config["slave_boards"][l["name"]]})
    # Remove duplicates (could happen is a team listed in a multiple_teams list is also added individually)
    slave_boards = []
    for fsb in full_slave_boards:
        if fsb["name"] not in [sb["name"] for sb in slave_boards]:
            slave_boards.append(fsb)
    sb_list = ", ".join([sb["name"] for sb in slave_boards])
    logging.debug("Master card is to be synced on %d slave boards (%s)" % (len(slave_boards), sb_list))

    # Check if slave cards are already attached to this master card
    linked_slave_cards = []
    master_card_attachments = get_card_attachments(config, master_card)
    for mca in master_card_attachments:
        # Get the details for each attached card
        url = "https://api.trello.com/1/cards/%s" % mca["card_shortUrl"]
        url += "?key=%s&token=%s" % (config["key"], config["token"])
        response = requests.request(
           "GET",
           url
        )
        attached_card = response.json()
        linked_slave_cards.append(attached_card)

    new_master_card_metadata = ""
    # Check if slave cards need to be unlinked
    if len(slave_boards) == 0 and len(linked_slave_cards) > 0:
        logging.debug("Master card has been unlinked from slave cards")
        # Information on the master card needs to be updated to remove the reference to the slave cards
        new_master_card_metadata = ""
        #TODO: Determine what to do with the slave cards

    num_new_cards = 0
    slave_cards = []
    if len(slave_boards) > 0:
        for sb in slave_boards:
            existing_slave_card = None
            for lsc in linked_slave_cards:
                for l in sb["lists"]:
                    if sb["lists"][l] == lsc["idList"]:
                        existing_slave_card = lsc
            if existing_slave_card:
                logging.debug("Slave card %s already exists on board %s" % (existing_slave_card["id"], sb["name"]))
                logging.debug(existing_slave_card)
                card = existing_slave_card
            else:
                # A new slave card needs to be created for this slave board
                num_new_cards += 1
                card = create_new_slave_card(config, master_card, sb)
                logging.debug(card["id"])
                # Update the master card by attaching the new slave card
                attach_slave_card_to_master_card(config, master_card, card)
            slave_cards.append(card)
        # Generate master card metadata based on the slave cards info
        new_master_card_metadata = generate_master_card_metadata(config, slave_cards)
        logging.info("This master card has %d slave cards (%d newly created)" % (len(slave_cards), num_new_cards))
    else:
        logging.info("This master card has no slave cards")

    # Update the master card's metadata if needed
    update_master_card_metadata(config, master_card, new_master_card_metadata)

    # Add a checklist for each team on the master card
    if len(slave_boards) > 0:
        master_card_checklists = get_card_checklists(config, master_card)
        create_checklist = True
        if master_card_checklists:
            logging.debug("Already %d checklists on this master card: %s" % (len(master_card_checklists), ", ".join([c["name"] for c in master_card_checklists])))
            for c in master_card_checklists:
                if "Involved Teams" == c["name"]:
                    #TODO: check if each team is on the checklist and update accordingly
                    create_checklist = False
                    logging.debug("Master card already contains a checklist name 'Involved Teams', skipping checklist creation")
        if create_checklist:
            cl = add_checklist_to_master_card(config, master_card)
            for sb in slave_boards:
                add_checklistitem_to_checklist(config, cl["id"], sb["name"])

        #TODO: Mark checklist item as Complete if slave card is Done

    return (len(slave_cards), num_new_cards)

def get_master_cards(config):
    logging.debug("Get list of cards on the master Trello board")
    url = "https://api.trello.com/1/boards/%s/cards" % config["master_board"]
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    response = requests.request(
       "GET",
       url
    )
    master_cards = response.json()
    logging.info("There are %d master cards that will be processed" % len(master_cards))
    return master_cards

def load_config():
    logging.debug("Load saved configuration")
    with open("data/config.json", "r") as json_file:
        config = json.load(json_file)
    config["slave_boards_ids"] = []
    for sb in config["slave_boards"]:
        config["slave_boards_ids"].append(config["slave_boards"][sb])
    config["multiple_teams_names"] = list(config["multiple_teams"].keys())
    logging.info("Config '%s' loaded" % config["name"])
    logging.debug(config)
    return config

def parse_args(arguments):
    parser = argparse.ArgumentParser(description="Sync cards between different teams' Trello boards")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--propagate", action='store_true', required=False, help="Propagate the master cards to the slave boards")
    group.add_argument("-cu", "--cleanup", action='store_true', required=False, help="Clean up all master cards and delete all cards from the slave boards (ONLY TO BE USED IN DEMO MODE)")

    # These arguments are only to be used in conjunction with --propagate
    parser.add_argument("-c", "--card", action='store', required=False, help="Specify which card to propagate. Only to be used in conjunction with --propagate.")

    # General arguments (can be used both with --propagate and --cleanup)
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    args = parser.parse_args(arguments)

    # Validate if the arguments are used correctly
    if args.cleanup and not logging.getLevelName(args.loglevel) == "DEBUG":
        logging.critical("The --cleanup argument can only be used in conjunction with --debug. Exiting...")
        sys.exit(3)
    if args.card and not args.propagate:
        logging.critical("The --card argument can only be used in conjunction with --propagate. Exiting...")
        sys.exit(4)
    if args.card and not (re.match("^[0-9a-zA-Z]{8}$", args.card) or re.match("^[0-9a-fA-F]{24}$", args.card)):
        logging.critical("The --card argument expects an 8 or 24-character card ID. Exiting...")
        sys.exit(5)

    # Configure logging level
    if args.loglevel:
        logging.basicConfig(level=args.loglevel)
        args.logging_level = logging.getLevelName(args.loglevel)

    logging.debug("These are the parsed arguments:\n'%s'" % args)
    return args

def init():
    if __name__ == "__main__":
        # Parse the provided command-line arguments
        args = parse_args(sys.argv[1:])

        # Load configuration values
        config = load_config()

        # Get list of cards on the master Trello board
        master_cards = get_master_cards(config)

        if args.cleanup:
            # Cleanup for demo purposes
            # Delete all the master card attachments and cards on the slave boards
            summary = cleanup_test_boards(config, master_cards)
        elif args.propagate:
            summary = {"master_cards": len(master_cards), "slave_card": 0, "new_slave_card": 0}
            if args.card:
                # Validate that this specific card is on the master board
                valid_master_card = False
                for master_card in master_cards:
                    if args.card in (master_card["id"], master_card["shortLink"]):
                        logging.debug("Card %s/%s is on the master board" % (master_card["id"], master_card["shortLink"]))
                        # Process that single card
                        valid_master_card = True
                        output = process_master_card(config, master_card)
                        summary["master_cards"] = 1
                        summary["slave_card"] += output[0]
                        summary["new_slave_card"] += output[1]
                        break
                if not valid_master_card:
                    #TODO: Check if this is a slave card to process the associated master card
                    logging.critical("Card %s is not located on the master board %s. Exiting..." % (args.card, config["master_board"]))
                    sys.exit(1)
            else:
                # Loop over all cards on the master board to sync the slave boards
                for idx, master_card in enumerate(master_cards):
                    logging.info("Processing master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
                    output = process_master_card(config, master_card)
                    summary["slave_card"] += output[0]
                    summary["new_slave_card"] += output[1]
        output_summary(args, summary)

init()
