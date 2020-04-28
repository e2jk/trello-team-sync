#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.

import logging
import json
import requests
import os
import sys

def delete_slave_cards(config):
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

def get_slave_card_information():
    logging.debug("Retrieve existing slave card information")
    slave_card = {}
    return slave_card

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
    linked_slave_boards = []
    linked_slave_cards = []

    # Check if slave cards need to be unlinked
    if len(slave_boards) == 0 and len(linked_slave_cards) > 0:
        logging.debug("Master card has been unlinked from slave cards")
        # Information on the master card needs to be updated to remove the reference to the slave cards
        new_master_card_metadata = ""
        #TODO: Determine what to do with the slave cards

    if len(slave_boards) > 0:
        slave_cards = []
        for sb in slave_boards:
            if sb["name"] not in linked_slave_boards:
                # A new slave card need to be created for this slave board
                card = create_new_slave_card(config, master_card, sb)
            else:
                # Retrieve status of existing slave card
                card = get_slave_card_information(linked_slave_cards[sb["name"]])
            slave_cards.append(card)
        # Generate master card metadata based on the slave cards info
        new_master_card_metadata = generate_master_card_metadata(slave_cards)

    # Update the master card's metadata if needed
    if new_master_card_metadata != current_master_card_metadata:
        logging.debug("Updating master card metadata")

    # Update the master card's checklist
    #TODO: Check if checklist exists
    #TODO: Verify each child board has a checklist item
    #TODO: Mark checklist item as Complete if child card is Done

def get_master_cards(config):
    logging.debug("Get list of cards on the master Trello board")
    dump_file = "temp/master_board.json"
    if os.path.exists(dump_file):
        logging.debug("Loading master cards from dump file")
        with open(dump_file) as in_file:
            master_cards = json.load(in_file)
    else:
        url = "https://api.trello.com/1/boards/%s/cards" % config["master_board"]
        url += "?key=%s&token=%s" % (config["key"], config["token"])
        response = requests.request(
           "GET",
           url
        )
        master_cards = response.json()
        with open(dump_file, "w") as out_file:
            json.dump(master_cards, out_file, sort_keys=True, indent=2)

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

def init():
    if __name__ == "__main__":
        logging.basicConfig(level=logging.DEBUG)
        # logging.basicConfig(level=logging.WARNING)
        logging.debug("Starting up")

        # Load configuration values
        config = load_config()

        # Cleanup for demo purposes
        do_clean_up = False
        if do_clean_up:
            # Delete all the cards on the slave boards
            delete_slave_cards(config)
            sys.exit(1)

        # Get list of cards on the master Trello board
        master_cards = get_master_cards(config)

        # Loop over all cards on the master board to sync the slave boards
        for master_card in master_cards:
            process_master_card(config, master_card)

init()
