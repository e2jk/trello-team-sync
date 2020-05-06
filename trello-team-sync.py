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
from slugify import slugify
import readline

METADATA_PHRASE = "DO NOT EDIT BELOW THIS LINE"
METADATA_SEPARATOR = "\n\n%s\n*== %s ==*\n" % ("-" * 32, METADATA_PHRASE)
cached_values = {"board": {}, "list": {}}

def rlinput(prompt, prefill=''):
    """Provide an editable input string
    Inspired from https://stackoverflow.com/a/36607077
    """
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()

def output_summary(args, summary):
    if not summary:
        return
    logging.info("="*64)
    if args.cleanup:
        logging.info("Summary%scleaned up %d master cards and deleted %d slave cards from %d slave boards/%d slave lists." % (
            " [DRY RUN]: would have " if args.dry_run else ": ",
            summary["cleaned_up_master_cards"],
            summary["deleted_slave_cards"],
            summary["erased_destination_boards"],
            summary["erased_destination_lists"]))
    elif args.propagate:
        logging.info("Summary%s: processed %d master cards (of which %d active) that have %d slave cards (of which %d %snew)." % (
            " [DRY RUN]" if args.dry_run else "",
            summary["master_cards"],
            summary["active_master_cards"],
            summary["slave_card"],
            summary["new_slave_card"],
            "would have been " if args.dry_run else ""))

def get_card_attachments(card):
    card_attachments = []
    if card["badges"]["attachments"] > 0:
        logging.debug("Getting %d attachments on master card %s" % (card["badges"]["attachments"], card["id"]))
        for a in perform_request("GET", "cards/%s/attachments" % card["id"]):
            # Only keep attachments that are links to other Trello cards
            card_shorturl_regex = "https://trello.com/c/([a-zA-Z0-9_-]{8})/.*"
            card_shorturl_regex_match = re.match(card_shorturl_regex, a["url"])
            if card_shorturl_regex_match:
                a["card_shortUrl"] = card_shorturl_regex_match.group(1)
                card_attachments.append(a)
    return card_attachments

def cleanup_test_boards(master_cards):
    logging.debug("Removing slave cards attachments on the master cards")
    cleaned_up_master_cards = 0
    for idx, master_card in enumerate(master_cards):
        logging.debug("="*64)
        logging.info("Cleaning up master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
        master_card_attachments = get_card_attachments(master_card)
        if len(master_card_attachments) > 0:
            cleaned_up_master_cards += 1
            for a in master_card_attachments:
                logging.debug("Deleting attachment %s from master card %s" %(a["id"], master_card["id"]))
                perform_request("DELETE", "cards/%s/attachments/%s" % (master_card["id"], a["id"]))

        # Removing teams checklist from the master card
        logging.debug("Retrieving checklists from card %s" % master_card["id"])
        for c in perform_request("GET", "cards/%s/checklists" % master_card["id"]):
            if "Involved Teams" == c["name"]:
                logging.debug("Deleting checklist %s (%s) from master card %s" %(c["name"], c["id"], master_card["id"]))
                perform_request("DELETE", "checklists/%s" % (c["id"]))

        # Removing metadata from the master cards
        update_master_card_metadata(master_card, "")

    logging.debug("Deleting slave cards")
    erased_destination_boards = []
    num_lists_to_cleanup = 0
    num_lists_inspected = 0
    num_erased_destination_lists = 0
    deleted_slave_cards = 0
    #TODO: In addition to cleaning up the lists defined in the configuration,
    # also clean up the other lists on the boards of the lists in the config
    destination_lists = []
    for dl in config["destination_lists"]:
        for l in config["destination_lists"][dl]:
            if l not in destination_lists:
                destination_lists.append(l)
                num_lists_to_cleanup += 1
    for l in destination_lists:
        logging.debug("="*64)
        num_lists_inspected += 1
        board_name = get_board_name_from_list(l)
        list_name = get_name("list", l)
        logging.debug("Retrieve cards from list %s|%s (list %d/%d)" % (board_name, list_name, num_lists_inspected, num_lists_to_cleanup))
        slave_cards = perform_request("GET", "lists/%s/cards" % l)
        logging.debug(slave_cards)
        logging.debug("List %s/%s has %d cards to delete" % (board_name, list_name, len(slave_cards)))
        if len(slave_cards) > 0:
            num_erased_destination_lists += 1
            if not board_name in erased_destination_boards:
                erased_destination_boards.append(board_name)
        for sc in slave_cards:
            logging.debug("Deleting slave card %s" % sc["id"])
            deleted_slave_cards += 1
            perform_request("DELETE", "cards/%s" % sc["id"])
    return {"cleaned_up_master_cards": cleaned_up_master_cards,
            "deleted_slave_cards": deleted_slave_cards,
            "erased_destination_boards": len(erased_destination_boards),
            "erased_destination_lists": num_erased_destination_lists}

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

def update_master_card_metadata(master_card, new_master_card_metadata):
    (main_desc, current_master_card_metadata) = split_master_card_metadata(master_card["desc"])
    if new_master_card_metadata != current_master_card_metadata:
        logging.debug("Updating master card metadata")
        if new_master_card_metadata:
            new_full_desc = "%s%s%s" % (main_desc, METADATA_SEPARATOR, new_master_card_metadata)
        else:
            # Also remove the metadata separator when removing the metadata
            new_full_desc = main_desc
        logging.debug(new_full_desc)
        perform_request("PUT", "cards/%s" % master_card["id"], {"desc": new_full_desc})

def get_name(record_type, record_id):
    global cached_values
    if record_id not in cached_values[record_type]:
        cached_values[record_type][record_id] = perform_request("GET", "%s/%s" % (record_type, record_id))["name"]
    return cached_values[record_type][record_id]

def get_board_name_from_list(list_id):
    #TODO: Cache the board ID from this list's ID
    board = perform_request("GET", "lists/%s" % list_id)
    return get_name("board", board["idBoard"])

def generate_master_card_metadata(slave_cards):
    mcm = ""
    for sc in slave_cards:
        mcm += "\n- '%s' on list '**%s|%s**'" % (sc["name"],
            get_name("board", sc["idBoard"]),
            get_name("list", sc["idList"]))
    logging.debug("New master card metadata: %s" % mcm)
    return mcm

def perform_request(method, url, query=None):
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

def create_new_slave_card(master_card, destination_list):
    logging.debug("Creating new slave card")
    query = {
       "idList": destination_list,
       "desc": "%s\n\nCreated from master card %s" % (master_card["desc"], master_card["shortUrl"]),
       "pos": "bottom",
       "idCardSource": master_card["id"],
        # Explicitly don't keep labels,members
        "keepFromSource": "attachments,checklists,comments,due,stickers"
    }
    new_slave_card = perform_request("POST", "cards", query)
    if new_slave_card:
        logging.debug("New slave card ID: %s" % new_slave_card["id"])
    return new_slave_card

def process_master_card(master_card):
    logging.debug("="*64)
    logging.debug("Process master card '%s'" % master_card["name"])
    # Check if this card is to be synced on a destination list
    destination_lists = []
    for l in master_card["labels"]:
        if l["name"] in config["destination_lists"]:
            for list in config["destination_lists"][l["name"]]:
                if list not in destination_lists:
                    destination_lists.append(list)
    logging.debug("Master card is to be synced on %d destination lists" % len(destination_lists))

    # Check if slave cards are already attached to this master card
    linked_slave_cards = []
    master_card_attachments = get_card_attachments(master_card)
    for mca in master_card_attachments:
        attached_card = perform_request("GET", "cards/%s" % mca["card_shortUrl"])
        linked_slave_cards.append(attached_card)

    new_master_card_metadata = ""
    # Check if slave cards need to be unlinked
    if len(destination_lists) == 0 and len(linked_slave_cards) > 0:
        logging.debug("Master card has been unlinked from slave cards")
        # Information on the master card needs to be updated to remove the reference to the slave cards
        new_master_card_metadata = ""
        #TODO: Determine what to do with the slave cards

    num_new_cards = 0
    slave_cards = []
    if len(destination_lists) > 0:
        for dl in destination_lists:
            existing_slave_card = None
            for lsc in linked_slave_cards:
                if dl == lsc["idList"]:
                    existing_slave_card = lsc
            if existing_slave_card:
                logging.debug("Slave card %s already exists on list %s" % (existing_slave_card["id"], dl))
                logging.debug(existing_slave_card)
                card = existing_slave_card
            else:
                # A new slave card needs to be created for this slave board
                num_new_cards += 1
                card = create_new_slave_card(master_card, dl)
                if card:
                    # Link cards between each other
                    logging.debug("Attaching master card %s to slave card %s" % (master_card["id"], card["id"]))
                    perform_request("POST", "cards/%s/attachments" % card["id"], {"url": master_card["url"]})
                    logging.debug("Attaching slave card %s to master card %s" % (card["id"], master_card["id"]))
                    perform_request("POST", "cards/%s/attachments" % master_card["id"], {"url": card["url"]})
            slave_cards.append(card)
        if card:
            # Generate master card metadata based on the slave cards info
            new_master_card_metadata = generate_master_card_metadata(slave_cards)
        logging.info("This master card has %d slave cards (%d newly created)" % (len(slave_cards), num_new_cards))
    else:
        logging.info("This master card has no slave cards")

    # Update the master card's metadata if needed
    update_master_card_metadata(master_card, new_master_card_metadata)

    # Add a checklist for each team on the master card
    if len(destination_lists) > 0 and not args.dry_run:
        logging.debug("Retrieving checklists from card %s" % master_card["id"])
        master_card_checklists = perform_request("GET", "cards/%s/checklists" % master_card["id"])
        create_checklist = True
        if master_card_checklists:
            logging.debug("Already %d checklists on this master card: %s" % (len(master_card_checklists), ", ".join([c["name"] for c in master_card_checklists])))
            for c in master_card_checklists:
                if "Involved Teams" == c["name"]:
                    #TODO: check if each team is on the checklist and update accordingly
                    create_checklist = False
                    logging.debug("Master card already contains a checklist name 'Involved Teams', skipping checklist creation")
        if create_checklist:
            logging.debug("Creating new checklist")
            cl = perform_request("POST", "cards/%s/checklists" % master_card["id"], {"name": "Involved Teams"})
            logging.debug(cl)
            for dl in destination_lists:
                #TODO: Support more friendly name in the config than the destination board's name
                # Use that list's board's name as checklist name
                checklistitem_name = get_board_name_from_list(dl)
                logging.debug("Adding new checklistitem '%s' to checklist %s" % (checklistitem_name, cl["id"]))
                new_checklistitem = perform_request("POST", "checklists/%s/checkItems" % cl["id"], {"name": checklistitem_name})
                logging.debug(new_checklistitem)

        #TODO: Mark checklist item as Complete if slave card is Done

    return (1 if len(destination_lists) > 0 else 0, len(slave_cards), num_new_cards)

def create_new_config():
    config = {"name": ""}
    print("Welcome to the new configuration assistant.")
    print("Trello key and token can be created at https://trello.com/app-key")
    print("Please:")

    # Trello key
    error_message = ""
    trello_key = None
    #TODO: propose reusing Trello key and token from existing config files
    while not trello_key:
        trello_key = input("%sEnter your Trello key ('q' to quit): " % error_message)
        if trello_key.lower() == "q":
            print("Exiting...")
            sys.exit(35)
        if not re.match("^[0-9a-fA-F]{32}$", trello_key):
            trello_key = None
            error_message = "Invalid Trello key, must be 32 characters. "
    config["key"] = trello_key

    # Trello token
    error_message = ""
    trello_token = None
    while not trello_token:
        trello_token = input("%sEnter your Trello token ('q' to quit): " % error_message)
        if trello_token.lower() == "q":
            print("Exiting...")
            sys.exit(36)
        if not re.match("^[0-9a-fA-F]{64}$", trello_token):
            trello_token = None
            error_message = "Invalid Trello token, must be 64 characters. "
    config["token"] = trello_token

    # Get the boards associated with the passed Trello credentials
    boards = perform_request("GET", "members/me/boards")
    print("These are your boards and their associated IDs:")
    print("           ID             |  Name")
    print("\n".join(["%s  |  %s" % (b["id"], b["name"]) for b in boards]))

    # Master board
    error_message = ""
    master_board = None
    while not master_board:
        master_board = input("%sEnter your master board ID ('q' to quit): " % error_message)
        if master_board.lower() == "q":
            print("Exiting...")
            sys.exit(37)
        if not re.match("^[0-9a-fA-F]{24}$", master_board):
            master_board = None
            error_message = "Invalid board ID, must be 24 characters. "
        elif master_board not in [b["id"] for b in boards]:
            master_board = None
            error_message = "This is not the ID of one of the boards you have access to. "
    config["master_board"] = master_board

    # Get the name of the selected board, and the lists associated with the other boards
    board_name = None
    lists_from_other_boards = []
    lists_output = ""
    for b in boards:
        if b["id"] == master_board:
            board_name = b["name"]
        else:
            lists_output += "\n\nLists from board '%s':\n           ID             |  Name" % b["name"]
            boards_lists = perform_request("GET", "boards/%s/lists" % b["id"])
            for l in boards_lists:
                lists_from_other_boards.append(l["id"])
                lists_output += "\n%s  |  '%s' (from board '%s')" % (l["id"], l["name"], b["name"])

    # Config name
    error_message = ""
    config_name = None
    while not config_name:
        # Propose the board name as config name
        config_name = rlinput("%sEnter a name for this new configuration ('q' to quit): " % error_message, board_name)
        if config_name.lower() == "q":
            print("Exiting...")
            sys.exit(38)
    config["name"] = config_name

    # Get the labels associated with the master board
    labels = perform_request("GET", "boards/%s/labels" % master_board)
    print("These are the labels from the selected board and their associated IDs:")
    print("           ID             |  Label")
    label_names = []
    for l in labels:
        if l["name"]:
            # Only propose labels that have names
            print("%s  |  '%s' (%s)" % (l["id"], l["name"], l["color"]))
            label_names.append(l["name"])

    # Associate labels with lists
    config["destination_lists"] = {}
    error_message = ""
    continue_label = "yes"
    label = None
    while continue_label == "yes":
        while not label:
            label = input("%sEnter a label name ('q' to quit): " % error_message)
            if label.lower() == "q":
                print("Exiting...")
                sys.exit(39)
            elif label not in label_names:
                label = None
                error_message = "This is not a valid label name for the selected board. "
        config["destination_lists"][label] = []
        # Get list ID to associate with this label
        error_message = ""
        list_id = None
        print("These are the lists associated to the other boards:\n%s" % lists_output)
        while not list_id:
            list_id = input("%sEnter the list ID you want to associate with label '%s' ('q' to quit): " % (error_message, label))
            if list_id.lower() == "q":
                print("Exiting...")
                sys.exit(40)
            if not re.match("^[0-9a-fA-F]{24}$", list_id):
                list_id = None
                error_message = "Invalid list ID, must be 24 characters. "
        config["destination_lists"][label].append(list_id)
        #TODO: Support labels that point to multiple lists

        error_message = ""
        continue_label = None
        while not continue_label:
            continue_label = input("%sDo you want to add a new label (Enter 'yes' or 'no', 'q' to quit): " % error_message)
            if continue_label.lower() == "q":
                print("Exiting...")
                sys.exit(41)
            if continue_label not in ("yes", "no"):
                continue_label = None
            label = None

    logging.debug(config)

    config_file = "data/config_%s.json" % slugify(config_name)
    while os.path.isfile(config_file):
        #TODO: ask the user to enter a new valid file name
        config_file += ".nxt"
    with open(config_file, 'w') as out_file:
        json.dump(config, out_file, indent=2)
    print("New configuration saved to file '%s'" % config_file)
    return config_file

def new_webhook():
    logging.debug("Creating a new webhook for master board %s" % config["master_board"])
    query = {
        #TODO: direct to our future web enpoint
        #TODO: pass config filename for easier retrieval when processing a webhook
        "callbackURL": "https://webhook.site/04b7baf0-1a59-41e2-b41a-245abeabc847?c=config",
        "idModel": config["master_board"]
    }
    webhooks = perform_request("POST", "webhooks", query)
    logging.debug(json.dumps(webhooks, indent=2))

def list_webhooks():
    logging.debug("Existing webhooks:")
    webhooks = perform_request("GET", "tokens/%s/webhooks" % config["token"])
    logging.debug(json.dumps(webhooks, indent=2))
    return webhooks

def delete_webhook():
    logging.debug("Delete existing webhook for master board %s" % config["master_board"])
    for w in list_webhooks():
        if w["idModel"] == config["master_board"]:
            # Delete the webhook for that config's master model
            perform_request("DELETE", "webhooks/%s" % w["id"])
            logging.debug("Webhook %s deleted" % w["id"])

def load_config(config_file):
    logging.debug("Loading configuration %s" % config_file)
    with open(config_file, "r") as json_file:
        config = json.load(json_file)
    logging.info("Config '%s' loaded" % config["name"])
    logging.debug(config)
    return config

def parse_args(arguments):
    parser = argparse.ArgumentParser(description="Sync cards between different teams' Trello boards")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--propagate", action='store_true', required=False, help="Propagate the master cards to the slave boards")
    group.add_argument("-cu", "--cleanup", action='store_true', required=False, help="Clean up all master cards and delete all cards from the slave boards (ONLY TO BE USED IN DEMO MODE)")
    group.add_argument("-nc", "--new-config", action='store_true', required=False, help="Create a new configuration file")
    group.add_argument("-w", "--webhook", choices=["new", "list", "delete"], action='store', required=False, help="Create new, list or delete existing webhooks")

    # These arguments are only to be used in conjunction with --propagate
    parser.add_argument("-c", "--card", action='store', required=False, help="Specify which master card to propagate. Only to be used in conjunction with --propagate")
    parser.add_argument("-l", "--list", action='store', required=False, help="Specify which master list to propagate. Only to be used in conjunction with --propagate")

    # General arguments (can be used both with --propagate and --cleanup)
    parser.add_argument("-dr", "--dry-run", action='store_true', required=False, help="Do not create, update or delete any records")
    parser.add_argument("-cfg", "--config", action='store', required=False, help="Path to the configuration file to use")
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

    # Check if the --card argument is a card URL
    if args.card:
        regex_match = re.match("^https://trello.com/c/([0-9a-zA-Z]{8})(/.*)?$", args.card)
        if regex_match:
            args.card = regex_match.group(1)

    # Validate if the arguments are used correctly
    if args.cleanup and not logging.getLevelName(args.loglevel) == "DEBUG":
        logging.critical("The --cleanup argument can only be used in conjunction with --debug. Exiting...")
        sys.exit(3)
    if args.webhook and not logging.getLevelName(args.loglevel) == "DEBUG":
        logging.critical("The --webhook argument can only be used in conjunction with --debug. Exiting...")
        sys.exit(9)
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
    if args.config and not os.path.isfile(args.config):
        logging.critical("The value passed in the --path argument is not a valid file path. Exiting...")
        sys.exit(8)

    # Configure logging level
    if args.loglevel:
        logging.basicConfig(level=args.loglevel)
        args.logging_level = logging.getLevelName(args.loglevel)

    logging.debug("These are the parsed arguments:\n'%s'" % args)
    return args

def init():
    if __name__ == "__main__":
        # Define as global variable to be used without passing to all functions
        global args
        global config
        # Parse the provided command-line arguments
        args = parse_args(sys.argv[1:])

        config_file = args.config
        if args.new_config:
            config_file = create_new_config()

        # Load configuration values
        if not config_file:
            config_file = "data/config.json"
        config = load_config(config_file)

        summary = None
        if args.cleanup:
            if not args.dry_run:
                # Cleanup deletes data, ensure the user is aware of that
                warning_acknowledged = False
                while not warning_acknowledged:
                    s = input("WARNING: this will delete all cards on the slave lists. Type 'YES' to confirm, or 'q' to quit: ")
                    if s.lower() == "q":
                        print("Exiting...")
                        sys.exit(34)
                    if s.lower() in ("yes", "oui", "ok", "yep", "no problemo", "aye"):
                        warning_acknowledged = True
            logging.debug("Get list of cards on the master Trello board")
            master_cards = perform_request("GET", "boards/%s/cards" % config["master_board"])
            # Delete all the master card attachments and cards on the slave boards
            summary = cleanup_test_boards(master_cards)
        elif args.propagate:
            summary = {"master_cards": 0, "active_master_cards": 0, "slave_card": 0, "new_slave_card": 0}
            if args.card:
                # Validate that this specific card is on the master board
                try:
                    master_card = perform_request("GET", "cards/%s" % args.card)
                except requests.exceptions.HTTPError:
                    logging.critical("Invalid card ID %s, card not found. Exiting..." % args.card)
                    sys.exit(33)
                if master_card["idBoard"] == config["master_board"]:
                    logging.debug("Card %s/%s is on the master board" % (master_card["id"], master_card["shortLink"]))
                    # Process that single card
                    output = process_master_card(master_card)
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
                    master_lists = perform_request("GET", "boards/%s/lists" % config["master_board"])
                    valid_master_list = False
                    for master_list in master_lists:
                        if args.list == master_list["id"]:
                            logging.debug("List %s is on the master board" % master_list["id"])
                            valid_master_list = True
                            # Get the list of cards on this master list
                            master_cards = perform_request("GET", "lists/%s/cards" % master_list["id"])
                            break
                    if not valid_master_list:
                        logging.critical("List %s is not on the master board %s. Exiting..." % (args.list, config["master_board"]))
                        sys.exit(32)
                else:
                    logging.debug("Get list of cards on the master Trello board")
                    master_cards = perform_request("GET", "boards/%s/cards" % config["master_board"])
                # Loop over all cards on the master board or list to sync the slave boards
                for idx, master_card in enumerate(master_cards):
                    logging.info("Processing master card %d/%d - %s" %(idx+1, len(master_cards), master_card["name"]))
                    output = process_master_card(master_card)
                    summary["master_cards"] = len(master_cards)
                    summary["active_master_cards"] += output[0]
                    summary["slave_card"] += output[1]
                    summary["new_slave_card"] += output[2]
        elif args.webhook:
            if args.webhook == "new":
                new_webhook()
            elif args.webhook == "list":
                list_webhooks()
            elif args.webhook == "delete":
                delete_webhook()
        output_summary(args, summary)

init()
