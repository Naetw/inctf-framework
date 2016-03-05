#!/usr/bin/env python
# -*- coding: utf-8 -*-

# "Standard library imports"
import json
import random
import subprocess
import sys

# "Imports from third party packages"
import MySQLdb
import MySQLdb.cursors

# "Imports from current project"
from settings import MYSQL_DATABASE_DB, MYSQL_DATABASE_PASSWORD, MYSQL_DATABASE_USER


def insert_config_values(config):
    db_obj = MySQLdb.connect(user=MYSQL_DATABASE_USER, passwd=MYSQL_DATABASE_PASSWORD,
                             db=MYSQL_DATABASE_DB,
                             cursorclass=MySQLdb.cursors.DictCursor)

    cursor = db_obj.cursor()

    # Very first, create the game. Copied from vm_reset_db.py
    new_game_id = random.randint(0, 1000000)
    cursor.execute("""INSERT INTO game (id) VALUES (%s)""",
                   (new_game_id,))

    # Insert team info from config
    print "Inserting team info into database"
    query = """INSERT INTO teams (team_name, services_ports_low, services_ports_high)
            VALUES (%s, %s, %s)"""
    teams = {}
    for team in config["teams"]:
        values = (team["name"], team["services_ports_low"],
                  team["services_ports_high"])
        cursor.execute(query, values)
        team["id"] = db_obj.insert_id()
        teams[team["name"]] = team

    config["teams"] = teams
    db_obj.commit()
    print "done"

    # Insert services info from config
    print "Inserting services info into database"
    query = """INSERT INTO services (name, internal_port, description, authors,
            flag_id_description, offset_external_port) VALUES (%s, %s, %s, %s, %s,
            %s)"""
    services = {}
    for service in config["services"]:
        description = service.get("description", "")
        flag_id_description = service.get("flag_id_description", "")
        values = (service["name"], service["internal_port"], description,
                  ''.join(service["authors"]), flag_id_description,
                  service["offset_external_port"])
        cursor.execute(query, values)
        service["id"] = db_obj.insert_id()
        services[service["name"]] = service

    config["services"] = services
    db_obj.commit()
    print "done"

    # Insert scripts details from config
    print "Inserting scripts info into database"
    query = """INSERT INTO scripts (name, type, service_id, is_working) VALUES (%s,
            %s, %s, %s)"""

    for script in config["scripts"]:
        is_working = script.get("is_working", 1)
        service_id = config["services"][script["service"]]["id"]
        values = (script["name"], script["type"], service_id, is_working)
        cursor.execute(query, values)

    db_obj.commit()
    print "done"

    # Insert location of service containers into DB
    print "Inserting services_locations info in database"
    query = """INSERT INTO services_locations (team_id, service_id, host_ip,
            host_port) VALUES (%s, %s, %s, %s)"""

    for location in config["services_location"]:
        team_id = config["teams"][location["team"]]["id"]
        service_id = config["services"][location["service"]]["id"]
        values = (team_id, service_id, location["host_ip"], location["host_port"])
        cursor.execute(query, values)

    db_obj.commit()
    print "done"

    # Insert containers info in DB
    print "Inserting container information into DB"
    query = """INSERT INTO containers (name, service_id, team_id, registry_namespace,
            type) VALUES (%s, %s, %s, %s, %s)"""

    for container in config["containers"]:
        team_id = config["teams"][container["team"]]["id"]
        service_id = config["services"][container["service"]]["id"]
        values = (container["name"], service_id, team_id, container["namespace"],
                  container["type"])
        cursor.execute(query, values)

    db_obj.commit()
    print "done"
    return


def run_command_with_shell(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=True)
    stdout, stderr = process.communicate()
    retcode = process.returncode
    return (stdout, stderr, retcode)


def recreate_database():
    print "Recreating tables in DB"
    command = "mysql -u " + MYSQL_DATABASE_USER + " -p" + MYSQL_DATABASE_PASSWORD + " " + \
              MYSQL_DATABASE_DB + "< database.sql"
    out, err, ret = run_command_with_shell(command)
    if ret != 0:
        print "DB recreate failed with exitcode %d." % (ret)
        print "Stdout: ", out
        print "Stderr: ", err
        sys.exit(1)

    print "done"
    return


def main():
    if len(sys.argv) != 2:
        print "Usage: %s CONFIG_FILE" % (sys.argv[0])
        sys.exit(0)

    fh = open(sys.argv[1])
    config = json.load(fh)
    fh.close()
    recreate_database()
    insert_config_values(config)


if __name__ == "__main__":
    main()
