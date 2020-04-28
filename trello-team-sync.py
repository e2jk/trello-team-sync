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

def delete_slave_cards(config, master_cards):
    logging.debug("Removing slave cards attachments on the master cards")
    for master_card in master_cards:
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

    logging.debug("Deleting slave cards")
    for sb in config["slave_boards"]:
        for l in config["slave_boards"][sb]:
            logging.debug("Retrieve cards from list %s/%s" % (sb, l))
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
                url = "https://api.trello.com/1/cards/%s" % sc["id"]
                url += "?key=%s&token=%s" % (config["key"], config["token"])
                response = requests.request(
                   "DELETE",
                   url
                )

def generate_master_card_metadata(slave_cards):
    mcm = ""
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
    slave_boards = []
    for l in master_card["labels"]:
        if l["name"] in config["slave_boards"]:
            slave_boards.append({"name": l["name"], "lists": config["slave_boards"][l["name"]]})
    sb_list = ", ".join([sb["name"] for sb in slave_boards])
    logging.debug("Master card is to be synced on %d slave boards (%s)" % (len(slave_boards), sb_list))

    # Verify if this master card is already linked to slave cards
    current_master_card_metadata = ""
    new_master_card_metadata = ""
    #TODO: Parse master card description for already linked slave cards IDs
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

    # Check if slave cards need to be unlinked
    if len(slave_boards) == 0 and len(linked_slave_cards) > 0:
        logging.debug("Master card has been unlinked from slave cards")
        # Information on the master card needs to be updated to remove the reference to the slave cards
        new_master_card_metadata = ""
        #TODO: Determine what to do with the slave cards

    if len(slave_boards) > 0:
        slave_cards = []
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
                card = create_new_slave_card(config, master_card, sb)
                logging.debug(card["id"])
                # Update the master card by attaching the new slave card
                attach_slave_card_to_master_card(config, master_card, card)
            slave_cards.append(card)
        # Generate master card metadata based on the slave cards info
        new_master_card_metadata = generate_master_card_metadata(slave_cards)

    # Update the master card's metadata if needed
    if new_master_card_metadata != current_master_card_metadata:
        logging.debug("Updating master card metadata")

    # Update the master card's checklist
    #TODO: Check if checklist exists
    #TODO: Verify each slave board has a checklist item
    #TODO: Mark checklist item as Complete if slave card is Done

def get_master_cards(config):
    logging.debug("Get list of cards on the master Trello board")
    url = "https://api.trello.com/1/boards/%s/cards" % config["master_board"]
    url += "?key=%s&token=%s" % (config["key"], config["token"])
    response = requests.request(
       "GET",
       url
    )
    master_cards = response.json()

    return master_cards

def load_config():
    logging.debug("Load saved configuration")
    with open("data/config.json", "r") as json_file:
        config = json.load(json_file)
    config["slave_boards_ids"] = []
    for sb in config["slave_boards"]:
        config["slave_boards_ids"].append(config["slave_boards"][sb])
    logging.debug(config)
    return config

def parse_args(arguments):
    parser = argparse.ArgumentParser(description="Sync cards between different teams' Trello boards")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--propagate", action='store_true', required=False, help="Propagate the master cards to the slave boards")
    group.add_argument("-cu", "--cleanup", action='store_true', required=False, help="Clean up all master cards and delete all cards from the slave boards (ONLY TO BE USED IN DEMO MODE)")

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
        sys.exit(1)

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
            delete_slave_cards(config, master_cards)
        elif args.propagate:
            # Loop over all cards on the master board to sync the slave boards
            for master_card in master_cards:
                process_master_card(config, master_card)
        else:
            # Should never happen
            logging.critical("Program called with invalid parameters. Exiting...")
            sys.exit(1)

init()
