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
        logging.info("Summary%scleaned up %d master cards and deleted %d slave cards from %d slave boards/%d slave lists." % (
            " [DRY RUN]: would have " if args.dry_run else ": ",
            summary["cleaned_up_master_cards"],
            summary["deleted_slave_cards"],
            summary["erased_slave_boards"],
            summary["erased_slave_lists"]))
    elif args.propagate:
        logging.info("Summary%s: processed %d master cards (of which %d active) that have %d slave cards (of which %d %snew)." % (
            " [DRY RUN]" if args.dry_run else "",
            summary["master_cards"],
            summary["active_master_cards"],
            summary["slave_card"],
            summary["new_slave_card"],
            "would have been " if args.dry_run else ""))

def remove_teams_checklist(config, master_card):
    master_card_checklists = get_card_checklists(config, master_card)
    for c in master_card_checklists:
        if "Involved Teams" == c["name"]:
            logging.debug("Deleting checklist %s (%s) from master card %s" %(c["name"], c["id"], master_card["id"]))
            perform_request(config, "DELETE", "checklists/%s" % (c["id"]))

def add_checklistitem_to_checklist(config, checklist_id, item_name):
    logging.debug("Adding new checklistitem %s to checklist %s" % (item_name, checklist_id))
    new_checklistitem = perform_request(config, "POST", "checklists/%s/checkItems" % checklist_id, {"name": item_name})
    logging.debug(new_checklistitem)
    return new_checklistitem

def add_checklist_to_master_card(config, master_card):
    logging.debug("Creating new checklist")
    new_checklist = perform_request(config, "POST", "cards/%s/checklists" % master_card["id"], {"name": "Involved Teams"})
    logging.debug(new_checklist)
    return new_checklist

def get_card_checklists(config, master_card):
    logging.debug("Retrieving checklists from card %s" % master_card["id"])
    return perform_request(config, "GET", "cards/%s/checklists" % master_card["id"])

def get_card_attachments(config, card):
    card_attachments = []
    if card["badges"]["attachments"] > 0:
        logging.debug("Getting %d attachments on master card %s" % (card["badges"]["attachments"], card["id"]))
        for a in perform_request(config, "GET", "cards/%s/attachments" % card["id"]):
            # Only keep attachments that are links to other Trello cards
            card_shorturl_regex = "https://trello.com/c/([a-zA-Z0-9_-]{8})/.*"
            card_shorturl_regex_match = re.match(card_shorturl_regex, a["url"])
            if card_shorturl_regex_match:
                a["card_shortUrl"] = card_shorturl_regex_match.group(1)
                card_attachments.append(a)
    return card_attachments

def cleanup_test_boards(config, master_cards):
    logging.debug("Removing slave cards attachments on the master cards")
    cleaned_up_master_cards = 0
    for idx, master_card in enumerate(master_cards):
        logging.debug("="*64)
        logging.info("Cleaning up master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
        master_card_attachments = get_card_attachments(config, master_card)
        if len(master_card_attachments) > 0:
            cleaned_up_master_cards += 1
            for a in master_card_attachments:
                logging.debug("Deleting attachment %s from master card %s" %(a["id"], master_card["id"]))
                perform_request(config, "DELETE", "cards/%s/attachments/%s" % (master_card["id"], a["id"]))

        # Removing teams checklist from the master card
        remove_teams_checklist(config, master_card)

        # Removing metadata from the master cards
        update_master_card_metadata(config, master_card, "")

    logging.debug("Deleting slave cards")
    erased_slave_boards = []
    num_lists_to_cleanup = 0
    num_lists_inspected = 0
    num_erased_slave_lists = 0
    deleted_slave_cards = 0
    for sb in config["slave_boards"]:
        for l in config["slave_boards"][sb]:
            num_lists_to_cleanup += 1
    for sb in config["slave_boards"]:
        for l in config["slave_boards"][sb]:
            logging.debug("="*64)
            num_lists_inspected += 1
            logging.debug("Retrieve cards from list %s|%s (list %d/%d)" % (sb, l, num_lists_inspected, num_lists_to_cleanup))
            slave_cards = perform_request(config, "GET", "lists/%s/cards" % config["slave_boards"][sb][l])
            logging.debug(slave_cards)
            logging.debug("List %s/%s has %d cards to delete" % (sb, l, len(slave_cards)))
            if len(slave_cards) > 0:
                num_erased_slave_lists += 1
                if not sb in erased_slave_boards:
                    erased_slave_boards.append(sb)
            for sc in slave_cards:
                logging.debug("Deleting slave card %s" % sc["id"])
                deleted_slave_cards += 1
                perform_request(config, "DELETE", "cards/%s" % sc["id"])
    return {"cleaned_up_master_cards": cleaned_up_master_cards,
            "deleted_slave_cards": deleted_slave_cards,
            "erased_slave_boards": len(erased_slave_boards),
            "erased_slave_lists": num_erased_slave_lists}

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
        perform_request(config, "PUT", "cards/%s" % master_card["id"], {"desc": new_full_desc})

def get_name(config, record_type, record_id):
    #TODO: Cache board/list names
    return perform_request(config, "GET", "%s/%s" % (record_type, record_id))["name"]

def generate_master_card_metadata(config, slave_cards):
    mcm = ""
    for sc in slave_cards:
        mcm += "\n- '%s' on list '**%s|%s**'" % (sc["name"],
            get_name(config, "board", sc["idBoard"]),
            get_name(config, "list", sc["idList"]))
    logging.debug("New master card metadata: %s" % mcm)
    return mcm

def perform_request(config, method, url, query=None):
    if method not in ("GET", "POST", "PUT", "DELETE"):
        logging.critical("HTTP method '%s' not supported. Exiting..." % method)
        sys.exit(30)
    url = "https://api.trello.com/1/%s" % url
    if args.dry_run and method != "GET":
        logging.debug("Skipping %s call to '%s' due to --dry-run parameter" % (method, url))
        return {}
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    response = requests.request(
        method,
        url,
        params=query
    )
    # Raise an exception if the response status code indicates an issue
    response.raise_for_status()
    return response.json()

def create_new_slave_card(config, master_card, slave_board):
    logging.debug("Creating new slave card")
    query = {
       "idList": slave_board["lists"]["backlog"],
       "desc": "%s\n\nCreated from master card %s" % (master_card["desc"], master_card["shortUrl"]),
       "pos": "bottom",
       "idCardSource": master_card["id"],
        # Explicitly don't keep labels,members
        "keepFromSource ": "attachments,checklists,comments,due,stickers"
    }
    new_slave_card = perform_request(config, "POST", "cards", query)
    if new_slave_card:
        logging.debug("New slave card ID: %s" % new_slave_card["id"])
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
        attached_card = perform_request(config, "GET", "cards/%s" % mca["card_shortUrl"])
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
                if card:
                    # Link cards between each other
                    logging.debug("Attaching master card %s to slave card %s" % (master_card["id"], card["id"]))
                    perform_request(config, "POST", "cards/%s/attachments" % card["id"], {"url": master_card["url"]})
                    logging.debug("Attaching slave card %s to master card %s" % (card["id"], master_card["id"]))
                    perform_request(config, "POST", "cards/%s/attachments" % master_card["id"], {"url": card["url"]})
            slave_cards.append(card)
        if card:
            # Generate master card metadata based on the slave cards info
            new_master_card_metadata = generate_master_card_metadata(config, slave_cards)
        logging.info("This master card has %d slave cards (%d newly created)" % (len(slave_cards), num_new_cards))
    else:
        logging.info("This master card has no slave cards")

    # Update the master card's metadata if needed
    update_master_card_metadata(config, master_card, new_master_card_metadata)

    # Add a checklist for each team on the master card
    if len(slave_boards) > 0 and not args.dry_run:
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

    return (1 if len(slave_boards) > 0 else 0, len(slave_cards), num_new_cards)

def load_config(config_file="data/config.json"):
    logging.debug("Loading configuration %s" % config_file)
    with open(config_file, "r") as json_file:
        config = json.load(json_file)
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
    parser.add_argument("-c", "--card", action='store', required=False, help="Specify which master card to propagate. Only to be used in conjunction with --propagate")
    parser.add_argument("-l", "--list", action='store', required=False, help="Specify which master list to propagate. Only to be used in conjunction with --propagate")

    # General arguments (can be used both with --propagate and --cleanup)
    parser.add_argument("-dr", "--dry-run", action='store_true', required=False, help="Do not create, update or delete any records")
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
    if args.list and not args.propagate:
        logging.critical("The --list argument can only be used in conjunction with --propagate. Exiting...")
        sys.exit(6)
    if args.list and not re.match("^[0-9a-fA-F]{24}$", args.list):
        logging.critical("The --list argument expects a 24-character list ID. Exiting...")
        sys.exit(7)

    # Configure logging level
    if args.loglevel:
        logging.basicConfig(level=args.loglevel)
        args.logging_level = logging.getLevelName(args.loglevel)

    logging.debug("These are the parsed arguments:\n'%s'" % args)
    return args

def init():
    if __name__ == "__main__":
        # Parse the provided command-line arguments
        global args # Define as global variable to be used without passing to all functions
        args = parse_args(sys.argv[1:])

        # Load configuration values
        config = load_config()

        if args.cleanup:
            # Cleanup for demo purposes
            logging.debug("Get list of cards on the master Trello board")
            master_cards = perform_request(config, "GET", "boards/%s/cards" % config["master_board"])
            # Delete all the master card attachments and cards on the slave boards
            summary = cleanup_test_boards(config, master_cards)
        elif args.propagate:
            summary = {"active_master_cards": 0, "slave_card": 0, "new_slave_card": 0}
            if args.card:
                # Validate that this specific card is on the master board
                try:
                    master_card = perform_request(config, "GET", "cards/%s" % args.card)
                except requests.exceptions.HTTPError:
                    logging.critical("Invalid card ID %s. Exiting..." % args.card)
                    sys.exit(33)
                if master_card["idBoard"] == config["master_board"]:
                    logging.debug("Card %s/%s is on the master board" % (master_card["id"], master_card["shortLink"]))
                    # Process that single card
                    output = process_master_card(config, master_card)
                    summary["master_cards"] = 1
                    summary["active_master_cards"] = output[0]
                    summary["slave_card"] += output[1]
                    summary["new_slave_card"] += output[2]
                else:
                    #TODO: Check if this is a slave card to process the associated master card
                    logging.critical("Card %s is not located on the master board %s. Exiting..." % (args.card, config["master_board"]))
                    sys.exit(31)
            else:
                if args.list:
                    # Validate that this specific list is on the master board
                    master_lists = perform_request(config, "GET", "boards/%s/lists" % config["master_board"])
                    valid_master_list = False
                    for master_list in master_lists:
                        if args.list == master_list["id"]:
                            logging.debug("List %s is on the master board" % master_list["id"])
                            valid_master_list = True
                            # Get the list of cards on this master list
                            master_cards = perform_request(config, "GET", "lists/%s/cards" % master_list["id"])
                            break
                    if not valid_master_list:
                        logging.critical("List %s is not on the master board %s. Exiting..." % (args.list, config["master_board"]))
                        sys.exit(32)
                else:
                    logging.debug("Get list of cards on the master Trello board")
                    master_cards = perform_request(config, "GET", "boards/%s/cards" % config["master_board"])
                # Loop over all cards on the master board or list to sync the slave boards
                for idx, master_card in enumerate(master_cards):
                    logging.info("Processing master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
                    output = process_master_card(config, master_card)
                    summary["master_cards"] = len(master_cards)
                    summary["active_master_cards"] += output[0]
                    summary["slave_card"] += output[1]
                    summary["new_slave_card"] += output[2]
        output_summary(args, summary)

init()
