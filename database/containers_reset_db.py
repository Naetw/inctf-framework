#!/usr/bin/env python
# -*- coding: utf-8 -*-

# "Standard library imports"
import json
import subprocess
import sys

# "Imports from current project"
from settings import MYSQL_DATABASE_DB, MYSQL_DATABASE_PASSWORD, MYSQL_DATABASE_USER


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


if __name__ == "__main__":
    main()
